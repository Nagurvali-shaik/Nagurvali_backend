from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.db.models import Q, Sum
from django.utils import timezone

from order.models import Order, OrderItem


SALE_STATUSES = {
    Order.Status.PAID,
    Order.Status.CONFIRMED,
    Order.Status.PROCESSING,
    Order.Status.SHIPPED,
    Order.Status.DELIVERED,
}

FAILED_STATUSES = {
    Order.Status.CANCELLED,
}


@dataclass(frozen=True)
class BadgeThresholds:
    customer_vip_orders: int = 20
    customer_vip_spending: Decimal = Decimal("1000.00")
    shop_owner_vip_revenue: Decimal = Decimal("2000.00")
    shop_owner_vip_orders: int = 200
    supplier_vip_units: int = 500
    supplier_vip_revenue: Decimal = Decimal("2000.00")
    marketer_vip_revenue: Decimal = Decimal("1500.00")
    courier_vip_deliveries: int = 30
    trusted_min_success_rate: Decimal = Decimal("0.95")
    trusted_max_refund_rate: Decimal = Decimal("0.03")
    trusted_min_account_days: int = 30
    vip_inactive_days: int = 180


def _is_suspended(user) -> bool:
    return not bool(getattr(user, "is_active", True))


def _is_phone_verified(user) -> bool:
    return bool(getattr(user, "is_verified", False))


def _has_merchant_id(user) -> bool:
    return bool(getattr(user, "merchant_id", None))


def _account_age_days(user) -> int:
    created_at = getattr(user, "created_at", None)
    if not created_at:
        return 0
    return max(0, (timezone.now() - created_at).days)


def _customer_metrics(user) -> tuple[int, Decimal, Optional[timezone.datetime]]:
    qs = Order.objects.filter(user=user, status__in=SALE_STATUSES)
    orders_count = qs.count()
    spending = qs.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    latest = qs.order_by("-created_at").values_list("created_at", flat=True).first()
    return orders_count, Decimal(str(spending)), latest


def _shop_owner_metrics(user) -> tuple[int, Decimal, int, int, Optional[timezone.datetime]]:
    base_qs = Order.objects.filter(shop__owner=user)
    success_qs = base_qs.filter(status__in=SALE_STATUSES)
    failed_qs = base_qs.filter(status__in=FAILED_STATUSES)
    revenue = success_qs.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    latest = base_qs.order_by("-created_at").values_list("created_at", flat=True).first()
    return success_qs.count(), Decimal(str(revenue)), success_qs.count(), failed_qs.count(), latest


def _supplier_metrics(user) -> tuple[int, Decimal, int, int, Optional[timezone.datetime]]:
    items_qs = OrderItem.objects.select_related("order", "product", "variant__product").filter(
        Q(product__supplier=user) | Q(variant__product__supplier=user)
    )
    success_items = items_qs.filter(order__status__in=SALE_STATUSES)
    failed_items = items_qs.filter(order__status__in=FAILED_STATUSES)
    units = 0
    revenue = Decimal("0.00")
    for item in success_items:
        product = item.product if item.product else (item.variant.product if item.variant else None)
        supplier_price = product.supplier_price if product and product.supplier_price is not None else item.price
        units += int(item.quantity)
        revenue += Decimal(str(supplier_price)) * Decimal(str(item.quantity))
    latest = (
        items_qs.order_by("-order__created_at")
        .values_list("order__created_at", flat=True)
        .first()
    )
    return units, revenue, success_items.count(), failed_items.count(), latest


def _marketer_metrics(user) -> tuple[Decimal, int, int, Optional[timezone.datetime]]:
    base_qs = Order.objects.filter(shop__marketers=user)
    success_qs = base_qs.filter(status__in=SALE_STATUSES)
    failed_qs = base_qs.filter(status__in=FAILED_STATUSES)
    revenue = success_qs.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    latest = base_qs.order_by("-created_at").values_list("created_at", flat=True).first()
    return Decimal(str(revenue)), success_qs.count(), failed_qs.count(), latest


def _courier_metrics(user) -> tuple[int, int, int]:
    deliveries = int(getattr(user, "total_jobs", 0) or 0)
    success = deliveries
    failed = 0
    return deliveries, success, failed


def _is_inactive(last_activity, threshold_days: int) -> bool:
    if not last_activity:
        return False
    return (timezone.now() - last_activity) > timedelta(days=threshold_days)


def _check_verified(user) -> bool:
    if _is_suspended(user):
        return False
    if getattr(user, "role", "CUSTOMER") == "CUSTOMER":
        return _is_phone_verified(user)
    return _is_phone_verified(user) and _has_merchant_id(user)


def _check_vip(user, t: BadgeThresholds) -> bool:
    role = getattr(user, "role", "CUSTOMER")
    if role == "CUSTOMER":
        total_orders, spending, last_activity = _customer_metrics(user)
        if _is_inactive(last_activity, t.vip_inactive_days):
            return False
        return total_orders >= t.customer_vip_orders or spending >= t.customer_vip_spending
    if role == "SHOP_OWNER":
        completed_orders, revenue, *_rest, last_activity = _shop_owner_metrics(user)
        if _is_inactive(last_activity, t.vip_inactive_days):
            return False
        return completed_orders >= t.shop_owner_vip_orders or revenue >= t.shop_owner_vip_revenue
    if role == "SUPPLIER":
        units, revenue, *_rest, last_activity = _supplier_metrics(user)
        if _is_inactive(last_activity, t.vip_inactive_days):
            return False
        return units >= t.supplier_vip_units or revenue >= t.supplier_vip_revenue
    if role == "MARKETER":
        revenue, *_rest, last_activity = _marketer_metrics(user)
        if _is_inactive(last_activity, t.vip_inactive_days):
            return False
        return revenue >= t.marketer_vip_revenue
    if role == "COURIER":
        deliveries, *_ = _courier_metrics(user)
        return deliveries >= t.courier_vip_deliveries
    return False


def _check_trusted(user, t: BadgeThresholds) -> bool:
    if _account_age_days(user) < t.trusted_min_account_days:
        return False

    role = getattr(user, "role", "CUSTOMER")
    success = 0
    failed = 0
    refunded = 0

    if role == "CUSTOMER":
        base_qs = Order.objects.filter(user=user)
        success = base_qs.filter(status__in=SALE_STATUSES).count()
        failed = base_qs.filter(status__in=FAILED_STATUSES).count()
        refunded = base_qs.filter(status=Order.Status.REFUNDED).count()
    elif role == "SHOP_OWNER":
        _, _, success, failed, _ = _shop_owner_metrics(user)
        refunded = Order.objects.filter(shop__owner=user, status=Order.Status.REFUNDED).count()
    elif role == "SUPPLIER":
        _, _, success, failed, _ = _supplier_metrics(user)
        refunded = OrderItem.objects.filter(
            Q(product__supplier=user) | Q(variant__product__supplier=user),
            order__status=Order.Status.REFUNDED,
        ).count()
    elif role == "MARKETER":
        _, success, failed, _ = _marketer_metrics(user)
        refunded = Order.objects.filter(shop__marketers=user, status=Order.Status.REFUNDED).count()
    elif role == "COURIER":
        _, success, failed = _courier_metrics(user)
        refunded = 0

    total = success + failed
    if total <= 0:
        return False
    success_rate = Decimal(success) / Decimal(total)
    refund_rate = Decimal(refunded) / Decimal(success if success > 0 else 1)
    no_fraud_flags = True
    return (
        success_rate >= t.trusted_min_success_rate
        and refund_rate <= t.trusted_max_refund_rate
        and no_fraud_flags
    )


def resolve_badge(user, persist: bool = True) -> str:
    thresholds = BadgeThresholds()
    if _check_trusted(user, thresholds):
        badge = "trusted"
    elif _check_vip(user, thresholds):
        badge = "vip"
    elif _check_verified(user):
        badge = "verified"
    else:
        badge = "none"

    if persist and getattr(user, "badge", None) != badge:
        user.badge = badge
        user.save(update_fields=["badge", "updated_at"])
    return badge

