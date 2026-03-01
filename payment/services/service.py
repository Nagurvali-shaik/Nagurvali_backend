# payments/services/payment_service.py
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction, models

from catalog.models import ProductVariant
from order.models import Order
from payment.models import Earning, LedgerEntry, Payment, Refund, PayoutRequest
from account.models import PaymentMethod
from .santimpay_sdk import SantimpaySDK
User = get_user_model()


class PaymentServiceError(Exception):
    """Base exception for payment service errors."""


class PaymentConfigurationError(PaymentServiceError):
    """Raised when required SantimPay settings are missing."""


class PaymentGatewayError(PaymentServiceError):
    """Raised when SantimPay API calls fail."""


@dataclass(frozen=True)
class PaymentInitResult:
    tx_id: str
    payment_url: str


class PaymentService:
    """High-level payment operations powered by SantimPay SDK."""

    def __init__(self, merchant_id: Optional[str] = None) -> None:
        resolved_merchant_id = self._resolve_merchant_id(merchant_id)
        private_key = self._get_setting("SANTIMPAY_PRIVATE_KEY")
        test_bed = self._get_bool_setting("SANTIMPAY_TEST_BED", default=True)

        self.default_success_url = self._get_setting("SANTIMPAY_SUCCESS_REDIRECT_URL", required=False)
        self.default_failure_url = self._get_setting("SANTIMPAY_FAILURE_REDIRECT_URL", required=False)
        self.default_cancel_url = self._get_setting("SANTIMPAY_CANCEL_REDIRECT_URL", required=False)
        self.default_notify_url = self._get_setting("SANTIMPAY_NOTIFY_URL", required=False)

        self.sdk = SantimpaySDK(
            merchant_id=resolved_merchant_id,
            private_key=private_key,
            test_bed=test_bed,
        )

    # -----------------------------
    # Payment & Direct Payment
    # -----------------------------
    @transaction.atomic
    def initiate_order_payment(
        self,
        order: Order,
        success_redirect_url: Optional[str] = None,
        failure_redirect_url: Optional[str] = None,
        notify_url: Optional[str] = None,
        cancel_redirect_url: Optional[str] = None,
        phone_number: str = "",
    ) -> PaymentInitResult:
        """
        Creates Payment record and initiates payment via SantimPay.
        """
        tx_id = order.payment_reference or str(order.id)

        # Create DB Payment record
        payment = Payment.objects.create(
            order=order,
            user=order.user,
            amount=order.total_amount,
            status=Payment.Status.PENDING,
            provider="SANTIMPAY",
            provider_reference=tx_id,
        )

        result = self.initiate_payment(
            amount=order.total_amount,
            payment_reason=f"Order payment {order.order_number}",
            tx_id=tx_id,
            success_redirect_url=success_redirect_url,
            failure_redirect_url=failure_redirect_url,
            notify_url=notify_url,
            cancel_redirect_url=cancel_redirect_url,
            phone_number=phone_number,
        )

        payment.provider_reference = result.tx_id
        payment.save(update_fields=["provider_reference", "updated_at"])

        # Save to order reference
        if order.payment_reference != result.tx_id:
            order.payment_reference = result.tx_id
            order.save(update_fields=["payment_reference", "updated_at"])

        return result

    def initiate_payment(
        self,
        amount: Decimal | float | int,
        payment_reason: str,
        success_redirect_url: Optional[str] = None,
        failure_redirect_url: Optional[str] = None,
        notify_url: Optional[str] = None,
        phone_number: str = "",
        cancel_redirect_url: Optional[str] = None,
        tx_id: Optional[str] = None,
    ) -> PaymentInitResult:
        normalized_amount = self._validate_amount(amount)
        reason = self._validate_reason(payment_reason)

        success_url = self._required_url(success_redirect_url or self.default_success_url, "success_redirect_url")
        failure_url = self._required_url(failure_redirect_url or self.default_failure_url, "failure_redirect_url")
        notify = self._required_url(notify_url or self.default_notify_url, "notify_url")

        generated_tx_id = tx_id or self.generate_tx_id()
        payment_url = self._call_gateway(
            self.sdk.generate_payment_url,
            tx_id=generated_tx_id,
            amount=float(normalized_amount),
            payment_reason=reason,
            success_redirect_url=success_url,
            failure_redirect_url=failure_url,
            notify_url=notify,
            phone_number=phone_number,
            cancel_redirect_url=cancel_redirect_url or self.default_cancel_url or "",
        )
        return PaymentInitResult(tx_id=generated_tx_id, payment_url=payment_url)

    def direct_payment(
        self,
        amount: Decimal | float | int,
        payment_reason: str,
        notify_url: Optional[str],
        phone_number: str,
        payment_method: str,
        tx_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_amount = self._validate_amount(amount)
        reason = self._validate_reason(payment_reason)
        notify = self._required_url(notify_url or self.default_notify_url, "notify_url")

        if not phone_number:
            raise PaymentServiceError("phone_number is required for direct payment")
        if not payment_method:
            raise PaymentServiceError("payment_method is required for direct payment")

        generated_tx_id = tx_id or self.generate_tx_id()
        return self._call_gateway(
            self.sdk.direct_payment,
            tx_id=generated_tx_id,
            amount=float(normalized_amount),
            payment_reason=reason,
            notify_url=notify,
            phone_number=phone_number,
            payment_method=payment_method,
        )

    # -----------------------------
    # Refunds
    # -----------------------------
    @transaction.atomic
    def initiate_refund(
        self,
        payment: Payment,
        amount: Decimal,
        reason: str,
        payment_method: str
    ) -> Refund:
        """
        Initiate partial or full refund.
        """
        if payment.status != Payment.Status.COMPLETED:
            raise PaymentServiceError("Only completed payments can be refunded")

        total_refunded = (
            Refund.objects.filter(payment=payment, status=Refund.Status.COMPLETED)
            .aggregate(total=models.Sum("amount"))["total"] or 0
        )
        if total_refunded + amount > payment.amount:
            raise PaymentServiceError("Refund exceeds original payment amount")

        refund = Refund.objects.create(
            payment=payment,
            amount=amount,
            status=Refund.Status.PROCESSING,
            reason=reason,
            requested_by=payment.user
        )

        # Call SantimPay payout
        response = self.payout_to_customer(
            amount=amount,
            payment_reason=f"Refund for order {payment.order.order_number}",
            phone_number=payment.user.phone,
            payment_method=payment_method,
            tx_id=f"REF-{payment.id}-{uuid.uuid4().hex[:8].upper()}"
        )

        refund.provider_reference = response.get("id")
        refund.save(update_fields=["provider_reference"])

        return refund

    @transaction.atomic
    def sync_refund_status(self, refund: Refund) -> Dict[str, Any]:
        if not refund.provider_reference:
            raise PaymentServiceError("Refund has no transaction reference")

        status_data = self.get_transaction_status(refund.provider_reference)
        gateway_status = self._extract_gateway_status(status_data)

        if gateway_status in {"SUCCESS", "COMPLETED", "PAID"}:
            refund.status = Refund.Status.COMPLETED
        elif gateway_status in {"FAILED", "CANCELLED"}:
            refund.status = Refund.Status.FAILED

        refund.save(update_fields=["status", "updated_at"])

        # Update payment and order if fully refunded
        payment = refund.payment
        total_refunded = (
            Refund.objects.filter(payment=payment, status=Refund.Status.COMPLETED)
            .aggregate(total=models.Sum("amount"))["total"] or 0
        )
        if total_refunded >= payment.amount:
            payment.status = Payment.Status.REFUNDED
            payment.save(update_fields=["status", "updated_at"])

            order = payment.order
            order.status = Order.Status.REFUNDED
            order.save(update_fields=["status", "updated_at"])

        return status_data

    # -----------------------------
    # Webhook / Sync
    # -----------------------------
    @transaction.atomic
    def sync_order_status(self, order: Order, tx_id: Optional[str] = None) -> Dict[str, Any]:
        resolved_tx_id = tx_id or order.payment_reference
        if not resolved_tx_id:
            raise PaymentServiceError("No transaction reference found for order")

        status_data = self.get_transaction_status(resolved_tx_id)
        gateway_status = self._extract_gateway_status(status_data)

        # Use strict transitions
        payment = Payment.objects.select_for_update().filter(order=order, provider_reference=resolved_tx_id).first()
        if not payment:
            raise PaymentServiceError("Payment record not found")

        if gateway_status in {"SUCCESS", "COMPLETED", "PAID"}:
            if self._can_transition(payment.status, Payment.Status.COMPLETED):
                payment.status = Payment.Status.COMPLETED
                payment.save(update_fields=["status", "updated_at"])
            if order.status != Order.Status.PAID:
                order.status = Order.Status.PAID
                order.save(update_fields=["status", "updated_at"])

        elif gateway_status in {"FAILED", "CANCELLED"}:
            if self._can_transition(payment.status, Payment.Status.FAILED):
                payment.status = Payment.Status.FAILED
                payment.save(update_fields=["status", "updated_at"])
            if order.status == Order.Status.PENDING:
                self._restock_order_variants(order)
                order.status = Order.Status.CANCELLED
                order.save(update_fields=["status", "updated_at"])

        return status_data

    @transaction.atomic
    def prepare_split_settlement(self, payment: Payment) -> Dict[str, Any]:
        if payment.status != Payment.Status.COMPLETED:
            raise PaymentServiceError("Split settlement is only allowed for completed payments")
        if payment.order.status != Order.Status.DELIVERED:
            raise PaymentServiceError("Split settlement is only allowed after delivery is completed")

        meta = dict(payment.metadata or {})
        settlement = meta.get("settlement", {})
        if settlement.get("prepared") is True:
            return settlement

        total_amount = self._to_decimal(payment.amount)
        commission_rate = Decimal("0.10")
        commission_amount = self._money(total_amount * commission_rate)
        supplier_amount = self._calculate_supplier_amount(payment)
        shop_owner_expected_amount = self._calculate_shop_owner_expected_amount(payment)

        dropshipper_user = payment.order.shop.owner
        supplier_user = self._resolve_supplier_user(payment, settlement)
        platform_user = self._resolve_platform_user()
        marketer_payouts = self._calculate_marketer_payouts(payment, total_amount)
        marketer_total = self._money(sum((p["amount"] for p in marketer_payouts), Decimal("0.00")))

        dropshipper_amount = self._money(
            total_amount - commission_amount - supplier_amount - marketer_total
        )
        if dropshipper_amount < Decimal("0.00"):
            raise PaymentServiceError(
                "Invalid split: platform + supplier + marketer payout exceeds payment amount"
            )

        allocations: Dict[str, Dict[str, Any]] = {}

        def add_allocation(user: Optional[User], amount: Decimal, role: str) -> None:
            if not user or amount <= Decimal("0.00"):
                return
            key = str(user.id)
            existing = allocations.get(key)
            if existing:
                existing["amount"] = str(self._money(self._to_decimal(existing["amount"]) + amount))
                existing["roles"] = sorted(set(existing.get("roles", []) + [role]))
                return
            allocations[key] = {
                "user_id": key,
                "amount": str(self._money(amount)),
                "status": "PENDING",
                "roles": [role],
            }

        if supplier_amount > 0 and not supplier_user:
            raise PaymentServiceError("Supplier payout amount exists but supplier user is not configured")

        add_allocation(supplier_user, supplier_amount, "SUPPLIER")
        for marketer in marketer_payouts:
            add_allocation(marketer["user"], marketer["amount"], "MARKETER")
        add_allocation(dropshipper_user, dropshipper_amount, "SHOP_OWNER")
        if platform_user:
            add_allocation(platform_user, commission_amount, "PLATFORM")

        self._ensure_ledger_entry(
            payment=payment,
            entry_type=LedgerEntry.EntryType.PAYMENT,
            amount=total_amount,
            description="Customer payment settled",
        )
        self._ensure_ledger_entry(
            payment=payment,
            entry_type=LedgerEntry.EntryType.COMMISSION,
            amount=commission_amount,
            description=f"Platform commission ({commission_rate * Decimal('100')}%)",
        )
        if supplier_amount > 0:
            self._ensure_ledger_entry(
                payment=payment,
                entry_type=LedgerEntry.EntryType.VENDOR_PAYOUT,
                amount=-supplier_amount,
                description="Supplier payout",
            )
        for marketer in marketer_payouts:
            self._ensure_ledger_entry(
                payment=payment,
                entry_type=LedgerEntry.EntryType.COMMISSION,
                amount=-marketer["amount"],
                description=f"Marketer commission user={marketer['user'].id}",
            )
        if dropshipper_amount > 0:
            self._ensure_ledger_entry(
                payment=payment,
                entry_type=LedgerEntry.EntryType.VENDOR_PAYOUT,
                amount=-dropshipper_amount,
                description="Dropshipper payout",
            )

        settlement_result: Dict[str, Any] = {
            "prepared": True,
            "processed": False,
            "earnings_recorded": False,
            "commission_rate": str(commission_rate),
            "total_amount": str(total_amount),
            "commission_amount": str(commission_amount),
            "platform_user_id": str(platform_user.id) if platform_user else None,
            "supplier_user_id": str(supplier_user.id) if supplier_user else None,
            "supplier_amount": str(supplier_amount),
            "marketer_total": str(marketer_total),
            "dropshipper_user_id": str(dropshipper_user.id),
            "shop_owner_expected_amount": str(shop_owner_expected_amount),
            "dropshipper_amount": str(dropshipper_amount),
            "allocations": allocations,
        }
        meta["settlement"] = settlement_result
        payment.metadata = meta
        payment.save(update_fields=["metadata", "updated_at"])
        return settlement_result

    @transaction.atomic
    def record_settlement_earnings(self, payment: Payment) -> Dict[str, Any]:
        if payment.order.status != Order.Status.DELIVERED:
            raise PaymentServiceError("Settlement earnings can be recorded only after delivery is completed")
        settlement = self.prepare_split_settlement(payment)
        if settlement.get("earnings_recorded") is True:
            return settlement

        allocations = settlement.get("allocations", {})
        for alloc in allocations.values():
            user_id = alloc.get("user_id")
            if not user_id:
                continue
            user = User.objects.filter(id=user_id).first()
            if not user:
                continue
            amount = self._money(self._to_decimal(alloc.get("amount", "0")))
            if amount <= Decimal("0.00"):
                continue
            roles = alloc.get("roles", [])
            role_value = "/".join(roles) if roles else ""
            merchant_snapshot = getattr(user, "merchant_id", "") or ""
            Earning.objects.update_or_create(
                user=user,
                payment=payment,
                defaults={
                    "order": payment.order,
                    "amount": amount,
                    "role": role_value,
                    "merchant_id_snapshot": merchant_snapshot,
                    "status": Earning.Status.AVAILABLE,
                    "metadata": {"allocation": alloc},
                },
            )

        settlement["earnings_recorded"] = True
        meta = dict(payment.metadata or {})
        meta["settlement"] = settlement
        payment.metadata = meta
        payment.save(update_fields=["metadata", "updated_at"])
        return settlement

    @transaction.atomic
    def request_total_user_payout(self, user: User) -> PayoutRequest:
        earnings = list(
            Earning.objects.select_for_update()
            .filter(user=user, status=Earning.Status.AVAILABLE)
            .order_by("created_at")
        )
        if not earnings:
            raise PaymentServiceError("No available earnings to payout")

        total_amount = self._money(sum((self._to_decimal(e.amount) for e in earnings), Decimal("0.00")))
        if total_amount <= Decimal("0.00"):
            raise PaymentServiceError("No available earnings to payout")

        payout_request = PayoutRequest.objects.create(
            user=user,
            payment=None,
            order=None,
            amount=total_amount,
            status=PayoutRequest.Status.PROCESSING,
            metadata={"earning_ids": [str(e.id) for e in earnings]},
        )
        try:
            payout_result = self._pay_user(
                user=user,
                amount=total_amount,
                payment_reason="Total earnings payout",
                tx_prefix="EARN",
            )
        except Exception as exc:
            payout_request.status = PayoutRequest.Status.FAILED
            payout_request.metadata = {"error": str(exc), "earning_ids": [str(e.id) for e in earnings]}
            payout_request.save(update_fields=["status", "metadata", "updated_at"])
            raise

        payout_request.payout_method = payout_result.get("method", "")
        payout_request.payout_account = payout_result.get("account", "")
        payout_request.provider_reference = (payout_result.get("provider_response") or {}).get("id")
        payout_request.metadata = {
            "earning_ids": [str(e.id) for e in earnings],
            "payout_result": payout_result,
        }
        payout_request.status = PayoutRequest.Status.COMPLETED
        payout_request.save(
            update_fields=[
                "payout_method",
                "payout_account",
                "provider_reference",
                "metadata",
                "status",
                "updated_at",
            ]
        )

        Earning.objects.filter(id__in=[e.id for e in earnings]).update(
            status=Earning.Status.PAID_OUT,
            payout_request=payout_request,
        )
        return payout_request

    @transaction.atomic
    def request_user_payout(self, payment: Payment, user: User) -> PayoutRequest:
        if payment.status != Payment.Status.COMPLETED:
            raise PaymentServiceError("Payout can only be requested for completed payments")

        settlement = self.prepare_split_settlement(payment)
        allocations = settlement.get("allocations", {})
        user_key = str(user.id)
        allocation = allocations.get(user_key)
        if not allocation:
            raise PaymentServiceError("No payout allocation found for this user")

        amount = self._money(self._to_decimal(allocation.get("amount", "0")))
        if amount <= Decimal("0.00"):
            raise PaymentServiceError("No payout amount available for this user")
        if allocation.get("status") == "COMPLETED":
            raise PaymentServiceError("Payout already completed for this user on this payment")

        payout_request, _ = PayoutRequest.objects.get_or_create(
            user=user,
            payment=payment,
            defaults={
                "order": payment.order,
                "amount": amount,
                "status": PayoutRequest.Status.REQUESTED,
            },
        )
        if payout_request.status == PayoutRequest.Status.COMPLETED:
            raise PaymentServiceError("Payout request already completed")

        payout_request.amount = amount
        payout_request.status = PayoutRequest.Status.PROCESSING
        payout_request.save(update_fields=["amount", "status", "updated_at"])

        reason = f"Payout for order {payment.order.order_number}"
        if allocation.get("roles"):
            reason = f"{'/'.join(allocation['roles'])} payout for order {payment.order.order_number}"

        try:
            payout_result = self._pay_user(
                user=user,
                amount=amount,
                payment_reason=reason,
                tx_prefix="PYO",
            )
        except Exception as exc:
            payout_request.status = PayoutRequest.Status.FAILED
            payout_request.metadata = {"error": str(exc)}
            payout_request.save(update_fields=["status", "metadata", "updated_at"])
            raise

        payout_request.payout_method = payout_result.get("method", "")
        payout_request.payout_account = payout_result.get("account", "")
        payout_request.provider_reference = (payout_result.get("provider_response") or {}).get("id")
        payout_request.metadata = payout_result
        payout_request.status = PayoutRequest.Status.COMPLETED
        payout_request.save(
            update_fields=[
                "payout_method",
                "payout_account",
                "provider_reference",
                "metadata",
                "status",
                "updated_at",
            ]
        )

        allocation["status"] = "COMPLETED"
        allocation["payout_request_id"] = str(payout_request.id)
        allocation["payout_response"] = payout_result
        settlement["processed"] = self._is_settlement_fully_paid(settlement)
        meta = dict(payment.metadata or {})
        meta["settlement"] = settlement
        payment.metadata = meta
        payment.save(update_fields=["metadata", "updated_at"])

        return payout_request

    @transaction.atomic
    def settle_split_payout(self, payment: Payment) -> Dict[str, Any]:
        """
        Split a successful payment using marketplace rules:
        - Platform keeps fixed 10%
        - Supplier gets initial product total
        - Marketer(s) get commission based on DB rate
        - Shop owner gets the remainder
        Idempotent across repeated webhook calls.
        """
        if payment.status != Payment.Status.COMPLETED:
            raise PaymentServiceError("Split payout is only allowed for completed payments")
        if payment.order.status != Order.Status.DELIVERED:
            raise PaymentServiceError("Split payout is only allowed after delivery is completed")

        meta = dict(payment.metadata or {})
        settlement = meta.get("settlement", {})
        if settlement.get("processed") is True:
            return settlement

        total_amount = self._to_decimal(payment.amount)
        commission_rate = Decimal("0.10")
        commission_amount = self._money(total_amount * commission_rate)
        supplier_amount = self._calculate_supplier_amount(payment)
        shop_owner_expected_amount = self._calculate_shop_owner_expected_amount(payment)

        dropshipper_user = payment.order.shop.owner
        supplier_user = self._resolve_supplier_user(payment, settlement)

        marketer_payouts = self._calculate_marketer_payouts(payment, total_amount)
        marketer_total = self._money(sum((p["amount"] for p in marketer_payouts), Decimal("0.00")))

        dropshipper_amount = self._money(
            total_amount - commission_amount - supplier_amount - marketer_total
        )
        if dropshipper_amount < Decimal("0.00"):
            raise PaymentServiceError(
                "Invalid split: platform + supplier + marketer payout exceeds payment amount"
            )

        supplier_result: Optional[Dict[str, Any]] = None
        dropshipper_result: Optional[Dict[str, Any]] = None
        marketer_results: List[Dict[str, Any]] = []

        if supplier_amount > 0:
            if not supplier_user:
                raise PaymentServiceError("Supplier payout amount exists but supplier user is not configured")
            supplier_result = self._pay_user(
                user=supplier_user,
                amount=supplier_amount,
                payment_reason=f"Supplier payout for order {payment.order.order_number}",
                tx_prefix="SUP",
            )

        for marketer in marketer_payouts:
            payout_response = self._pay_user(
                user=marketer["user"],
                amount=marketer["amount"],
                payment_reason=f"Marketer commission for order {payment.order.order_number}",
                tx_prefix="MKT",
            )
            marketer_results.append(
                {
                    "user_id": str(marketer["user"].id),
                    "rate": str(marketer["rate"]),
                    "amount": str(marketer["amount"]),
                    "payout_response": payout_response,
                }
            )

        if dropshipper_amount > 0:
            dropshipper_result = self._pay_user(
                user=dropshipper_user,
                amount=dropshipper_amount,
                payment_reason=f"Dropshipper payout for order {payment.order.order_number}",
                tx_prefix="DSP",
            )

        self._ensure_ledger_entry(
            payment=payment,
            entry_type=LedgerEntry.EntryType.PAYMENT,
            amount=total_amount,
            description="Customer payment settled",
        )
        self._ensure_ledger_entry(
            payment=payment,
            entry_type=LedgerEntry.EntryType.COMMISSION,
            amount=commission_amount,
            description=f"Platform commission ({commission_rate * Decimal('100')}%)",
        )
        if supplier_amount > 0:
            self._ensure_ledger_entry(
                payment=payment,
                entry_type=LedgerEntry.EntryType.VENDOR_PAYOUT,
                amount=-supplier_amount,
                description="Supplier payout",
            )
        for marketer in marketer_payouts:
            self._ensure_ledger_entry(
                payment=payment,
                entry_type=LedgerEntry.EntryType.COMMISSION,
                amount=-marketer["amount"],
                description=f"Marketer commission user={marketer['user'].id}",
            )
        if dropshipper_amount > 0:
            self._ensure_ledger_entry(
                payment=payment,
                entry_type=LedgerEntry.EntryType.VENDOR_PAYOUT,
                amount=-dropshipper_amount,
                description="Dropshipper payout",
            )

        settlement_result: Dict[str, Any] = {
            "processed": True,
            "commission_rate": str(commission_rate),
            "total_amount": str(total_amount),
            "commission_amount": str(commission_amount),
            "supplier_user_id": str(supplier_user.id) if supplier_user else None,
            "supplier_amount": str(supplier_amount),
            "marketer_total": str(marketer_total),
            "marketer_payouts": marketer_results,
            "dropshipper_user_id": str(dropshipper_user.id),
            "shop_owner_expected_amount": str(shop_owner_expected_amount),
            "dropshipper_amount": str(dropshipper_amount),
            "supplier_payout_response": supplier_result,
            "dropshipper_payout_response": dropshipper_result,
        }
        meta["settlement"] = settlement_result
        payment.metadata = meta
        payment.save(update_fields=["metadata", "updated_at"])
        return settlement_result

    # -----------------------------
    # Helper / SDK
    # -----------------------------
    def payout_to_customer(
        self,
        amount: Decimal | float | int,
        payment_reason: str,
        phone_number: str,
        payment_method: str,
        notify_url: Optional[str] = None,
        tx_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_amount = self._validate_amount(amount)
        reason = self._validate_reason(payment_reason)
        notify = self._required_url(notify_url or self.default_notify_url, "notify_url")

        if not phone_number:
            raise PaymentServiceError("phone_number is required for payout")
        if not payment_method:
            raise PaymentServiceError("payment_method is required for payout")

        generated_tx_id = tx_id or self.generate_tx_id()
        return self._call_gateway(
            self.sdk.send_to_customer,
            tx_id=generated_tx_id,
            amount=float(normalized_amount),
            payment_reason=reason,
            phone_number=phone_number,
            payment_method=payment_method,
            notify_url=notify,
        )

    def get_transaction_status(self, tx_id: str) -> Dict[str, Any]:
        if not tx_id:
            raise PaymentServiceError("tx_id is required")
        return self._call_gateway(self.sdk.check_transaction_status, tx_id=tx_id)

    # -----------------------------
    # Status / Validations
    # -----------------------------
    @staticmethod
    def _can_transition(current: str, target: str) -> bool:
        allowed = {
            "PENDING": {"PROCESSING", "COMPLETED", "FAILED"},
            "PROCESSING": {"COMPLETED", "FAILED"},
            "COMPLETED": {"REFUNDED"},
            "FAILED": set(),
            "REFUNDED": set(),
        }
        return target in allowed.get(current, set())

    @staticmethod
    def generate_tx_id(prefix: str = "TXN") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:20].upper()}"

    def _get_setting(self, key: str, required: bool = True) -> str:
        value = getattr(settings, key, None) or os.getenv(key)
        if required and not value:
            raise PaymentConfigurationError(
                f"Missing payment configuration: {key}. Set it in Django settings or environment variables."
            )
        return value or ""

    def _resolve_merchant_id(self, merchant_id: Optional[str]) -> str:
        if merchant_id:
            decoded = User.decode_merchant_id(str(merchant_id))
            if decoded:
                return decoded
            raise PaymentConfigurationError("Invalid merchant_id in database")
        return self._get_setting("SANTIMPAY_MERCHANT_ID")

    @staticmethod
    def _get_bool_setting(key: str, default: bool = False) -> bool:
        value = getattr(settings, key, None)
        if value is None:
            raw_env = os.getenv(key)
            if raw_env is None:
                return default
            value = raw_env

        if isinstance(value, bool):
            return value

        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _validate_amount(amount: Decimal | float | int) -> Decimal:
        dec = Decimal(str(amount))
        if dec <= 0:
            raise PaymentServiceError("amount must be greater than 0")
        return dec

    @staticmethod
    def _validate_reason(payment_reason: str) -> str:
        reason = (payment_reason or "").strip()
        if not reason:
            raise PaymentServiceError("payment_reason is required")
        return reason

    @staticmethod
    def _required_url(value: Optional[str], field_name: str) -> str:
        if not value:
            raise PaymentConfigurationError(
                f"{field_name} is required. Provide it in method args or configure it in settings."
            )
        return value

    @staticmethod
    def _extract_gateway_status(status_data: Dict[str, Any]) -> str:
        candidates = [
            status_data.get("status"),
            status_data.get("transactionStatus"),
            status_data.get("paymentStatus"),
        ]

        data = status_data.get("data")
        if isinstance(data, dict):
            candidates.extend(
                [
                    data.get("status"),
                    data.get("transactionStatus"),
                    data.get("paymentStatus"),
                ]
            )

        for value in candidates:
            if value:
                return str(value).upper()

        return "UNKNOWN"

    def _pay_user(
        self,
        user: User,
        amount: Decimal,
        payment_reason: str,
        tx_prefix: str,
    ) -> Dict[str, Any]:
        payout_info = self._resolve_payout_target(user)
        tx_id = self.generate_tx_id(prefix=tx_prefix)
        response = self.payout_to_customer(
            amount=amount,
            payment_reason=payment_reason,
            phone_number=payout_info["account"],
            payment_method=payout_info["method"],
            tx_id=tx_id,
        )
        return {
            "tx_id": tx_id,
            "method": payout_info["method"],
            "account": payout_info["account"],
            "provider_response": response,
        }

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        return Decimal(str(value))

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _resolve_supplier_user(self, payment: Payment, settlement_meta: Dict[str, Any]) -> Optional[User]:
        supplier_id = settlement_meta.get("supplier_user_id")
        if supplier_id:
            return User.objects.filter(id=supplier_id).first()

        payment_supplier_id = (payment.metadata or {}).get("supplier_user_id")
        if payment_supplier_id:
            return User.objects.filter(id=payment_supplier_id).first()

        supplier_ids = set()
        for item in payment.order.items.select_related("product", "variant__product").all():
            product = item.product if item.product else (item.variant.product if item.variant else None)
            if product and getattr(product, "supplier_id", None):
                supplier_ids.add(str(product.supplier_id))
        if len(supplier_ids) == 1:
            return User.objects.filter(id=supplier_ids.pop()).first()
        return None

    def _calculate_supplier_amount(self, payment: Payment) -> Decimal:
        settlement = (payment.metadata or {}).get("settlement", {})
        explicit_supplier_amount = settlement.get("supplier_amount") or (payment.metadata or {}).get("supplier_amount")
        if explicit_supplier_amount is not None:
            amount = self._money(self._to_decimal(explicit_supplier_amount))
            if amount < Decimal("0.00"):
                raise PaymentServiceError("supplier_amount cannot be negative")
            return amount

        total = Decimal("0.00")
        for item in payment.order.items.select_related("product", "variant").all():
            product = item.product if item.product else (item.variant.product if item.variant else None)
            if not product:
                continue
            supplier_price = product.supplier_price if product.supplier_price is not None else item.price
            if supplier_price is None:
                continue
            total += self._to_decimal(supplier_price) * Decimal(str(item.quantity))
        return self._money(total)

    def _calculate_shop_owner_expected_amount(self, payment: Payment) -> Decimal:
        total = Decimal("0.00")
        for item in payment.order.items.select_related("product", "variant").all():
            product = item.product if item.product else (item.variant.product if item.variant else None)
            if not product:
                continue
            owner_price = product.shop_owner_price if product.shop_owner_price is not None else item.price
            if owner_price is None:
                continue
            total += self._to_decimal(owner_price) * Decimal(str(item.quantity))
        return self._money(total)

    def _calculate_marketer_payouts(self, payment: Payment, total_amount: Decimal) -> List[Dict[str, Any]]:
        from marketer.models import MarketerContract

        payouts: List[Dict[str, Any]] = []
        order_items = payment.order.items.select_related("marketer_contract", "product").all()
        for item in order_items:
            contract = getattr(item, "marketer_contract", None)
            if not contract or not contract.is_active():
                continue
            if item.product and item.product.shop_id != contract.shop_id:
                continue
            rate = self._normalize_marketer_rate(self._to_decimal(contract.commission_rate))
            if rate <= Decimal("0.00"):
                continue
            amount = self._money(self._to_decimal(item.total) * rate)
            if amount <= Decimal("0.00"):
                continue
            payouts.append(
                {
                    "user": contract.marketer,
                    "rate": rate,
                    "amount": amount,
                    "contract_id": str(contract.id),
                    "order_item_id": str(item.id),
                }
            )
        return payouts

    def _restock_order_variants(self, order: Order) -> None:
        qty_by_variant: Dict[str, int] = {}
        for item in order.items.select_related("variant").all():
            if not item.variant_id:
                continue
            key = str(item.variant_id)
            qty_by_variant[key] = qty_by_variant.get(key, 0) + int(item.quantity)

        if not qty_by_variant:
            return

        variants = ProductVariant.objects.select_for_update().filter(id__in=qty_by_variant.keys())
        for variant in variants:
            variant.stock += qty_by_variant[str(variant.id)]
            variant.save(update_fields=["stock", "updated_at"])

    @staticmethod
    def _normalize_marketer_rate(raw_value: Decimal) -> Decimal:
        if raw_value <= Decimal("0"):
            return Decimal("0")
        if raw_value <= Decimal("1"):
            return raw_value
        if raw_value <= Decimal("100"):
            return raw_value / Decimal("100")
        return Decimal("1")

    def _resolve_payout_target(self, user: User) -> Dict[str, str]:
        preferred = list(
            PaymentMethod.objects.filter(shop_owner=user).order_by("created_at")
        )
        for payment_method in preferred:
            if payment_method.payment_type == "BANK" and payment_method.account_number:
                return {"method": "BANK", "account": payment_method.account_number}
            if payment_method.payment_type in {"TELEBIRR", "MPESA"} and payment_method.phone_number:
                return {"method": payment_method.payment_type, "account": payment_method.phone_number}

        if getattr(user, "bank_account_number", None):
            return {"method": "BANK", "account": user.bank_account_number}
        if getattr(user, "phone_number", None):
            default_mobile_method = getattr(settings, "DEFAULT_MOBILE_PAYOUT_METHOD", "TELEBIRR")
            return {"method": default_mobile_method, "account": user.phone_number}

        raise PaymentServiceError(
            f"No payout destination found for user {user.id}. "
            "Set a PaymentMethod or bank/phone details."
        )

    def _resolve_platform_user(self) -> Optional[User]:
        platform_user_id = getattr(settings, "PLATFORM_USER_ID", None) or os.getenv("PLATFORM_USER_ID")
        platform_user = None
        if platform_user_id:
            platform_user = User.objects.filter(id=platform_user_id).first()
        platform_user_email = getattr(settings, "PLATFORM_USER_EMAIL", None) or os.getenv("PLATFORM_USER_EMAIL")
        if not platform_user and platform_user_email:
            platform_user = User.objects.filter(email=platform_user_email).first()
        if platform_user and not getattr(platform_user, "merchant_id", None):
            configured_merchant = getattr(settings, "PLATFORM_MERCHANT_ID", None) or os.getenv("PLATFORM_MERCHANT_ID")
            if configured_merchant:
                platform_user.merchant_id = configured_merchant
                platform_user.save(update_fields=["merchant_id", "updated_at"])
        return platform_user

    @staticmethod
    def _is_settlement_fully_paid(settlement: Dict[str, Any]) -> bool:
        allocations = settlement.get("allocations", {})
        if not allocations:
            return False
        for allocation in allocations.values():
            amount = Decimal(str(allocation.get("amount", "0")))
            if amount <= Decimal("0"):
                continue
            if allocation.get("status") != "COMPLETED":
                return False
        return True

    def _ensure_ledger_entry(
        self,
        payment: Payment,
        entry_type: str,
        amount: Decimal,
        description: str,
    ) -> None:
        LedgerEntry.objects.get_or_create(
            order=payment.order,
            payment=payment,
            entry_type=entry_type,
            description=description,
            defaults={"amount": amount},
        )

    @staticmethod
    def _call_gateway(func, **kwargs):
        try:
            return func(**kwargs)
        except PaymentServiceError:
            raise
        except Exception as exc:
            message = str(exc).strip()
            if not message:
                message = "Payment provider request failed"
            raise PaymentGatewayError(message) from exc
