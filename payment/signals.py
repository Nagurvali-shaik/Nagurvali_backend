import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from order.models import Order
from payment.models import Payment
from payment.services.service import PaymentService, PaymentServiceError

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Order)
def _cache_previous_order_status(sender, instance: Order, **kwargs):
    if not instance.pk:
        instance._payment_previous_status = None
        return
    instance._payment_previous_status = (
        Order.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    )


@receiver(post_save, sender=Order)
def _record_settlement_earnings_on_delivery(sender, instance: Order, **kwargs):
    previous = getattr(instance, "_payment_previous_status", None)
    if previous == instance.status or instance.status != Order.Status.DELIVERED:
        return

    payment = (
        Payment.objects.select_related("order__shop__owner")
        .filter(order=instance, status=Payment.Status.COMPLETED)
        .order_by("-updated_at")
        .first()
    )
    if not payment:
        return

    merchant_id = (payment.metadata or {}).get("merchant_id") or getattr(
        getattr(instance.shop, "owner", None), "merchant_id", ""
    )
    if not merchant_id:
        logger.warning("Skipping settlement earnings for order=%s: merchant_id missing", instance.id)
        return

    try:
        PaymentService(merchant_id=merchant_id).record_settlement_earnings(payment)
    except PaymentServiceError:
        logger.exception("Failed to record settlement earnings for order=%s", instance.id)
