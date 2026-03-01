from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _

from .models import Payment, Refund, LedgerEntry, WebhookLog, PayoutRequest, Earning
from .services.service import PaymentService, PaymentServiceError


def _refund_service(refund):
	merchant_id = getattr(getattr(refund.payment.order.shop, "owner", None), "merchant_id", None)
	if not merchant_id:
		raise PaymentServiceError("Shop owner merchant_id is required for payment")
	return PaymentService(merchant_id=merchant_id)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
	list_display = ("id", "order", "user", "amount", "status", "provider", "provider_reference", "created_at")
	list_filter = ("status", "provider")
	search_fields = ("provider_reference", "order__order_number", "user__email")


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
	list_display = ("id", "payment", "amount", "status", "requested_by", "provider_reference", "created_at")
	list_filter = ("status",)
	search_fields = ("provider_reference", "payment__provider_reference", "requested_by__email")
	actions = ("approve_refunds", "reject_refunds", "execute_refunds", "sync_refunds")

	def approve_refunds(self, request, queryset):
		updated = queryset.update(status=Refund.Status.APPROVED)
		self.message_user(request, _("%d refunds marked as approved.") % updated, messages.SUCCESS)

	approve_refunds.short_description = "Approve selected refunds"

	def reject_refunds(self, request, queryset):
		updated = queryset.update(status=Refund.Status.REJECTED)
		self.message_user(request, _("%d refunds marked as rejected.") % updated, messages.SUCCESS)

	reject_refunds.short_description = "Reject selected refunds"

	def execute_refunds(self, request, queryset):
		"""Trigger payout for APPROVED refunds via the payment service."""
		succeeded = 0
		failed = 0
		for refund in queryset.select_related("payment__order__shop__owner", "requested_by").all():
			if refund.status != Refund.Status.APPROVED:
				failed += 1
				continue
			try:
				service = _refund_service(refund)
				target_user = refund.requested_by or refund.payment.user
				payout_info = service._resolve_payout_target(target_user)
				phone = payout_info.get("account")
				method = payout_info.get("method")
				tx_id = f"REF-{refund.payment.id}-{refund.id.hex[:8].upper()}"
				response = service.payout_to_customer(
					amount=refund.amount,
					payment_reason=refund.reason or f"Refund for order {refund.payment.order.order_number}",
					phone_number=phone,
					payment_method=method,
					tx_id=tx_id,
				)
				refund.provider_reference = response.get("id")
				refund.status = Refund.Status.PROCESSING
				metadata = dict(refund.metadata or {})
				metadata.setdefault("provider_response", {})
				metadata["provider_response"].update(response)
				refund.metadata = metadata
				refund.save(update_fields=["provider_reference", "status", "metadata", "updated_at"])
				succeeded += 1
			except PaymentServiceError as exc:
				failed += 1
				self.message_user(request, _("Failed to execute refund %(id)s: %(err)s") % {"id": refund.id, "err": str(exc)}, messages.ERROR)
			except Exception as exc:
				failed += 1
				self.message_user(request, _("Unexpected error executing refund %(id)s: %(err)s") % {"id": refund.id, "err": str(exc)}, messages.ERROR)

		self.message_user(request, _("Refunds executed: %(ok)d, failed: %(bad)d") % {"ok": succeeded, "bad": failed}, messages.INFO)

	execute_refunds.short_description = "Execute selected approved refunds (payout)"

	def sync_refunds(self, request, queryset):
		synced = 0
		errors = 0
		for refund in queryset.select_related("payment__order__shop__owner").all():
			if not refund.provider_reference:
				errors += 1
				continue
			try:
				service = _refund_service(refund)
				service.sync_refund_status(refund)
				synced += 1
			except Exception as exc:
				errors += 1
				self.message_user(request, _("Failed to sync refund %(id)s: %(err)s") % {"id": refund.id, "err": str(exc)}, messages.ERROR)

		self.message_user(request, _("Refunds synced: %(ok)d, errored: %(bad)d") % {"ok": synced, "bad": errors}, messages.INFO)


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
	list_display = ("id", "order", "payment", "entry_type", "amount", "created_at")
	list_filter = ("entry_type",)


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
	list_display = ("id", "provider", "event_type", "reference", "processed", "created_at")
	list_filter = ("provider", "processed")


@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
	list_display = ("id", "user", "payment", "amount", "status", "provider_reference", "created_at")
	list_filter = ("status",)
	search_fields = ("user__email", "payment__provider_reference", "provider_reference")


@admin.register(Earning)
class EarningAdmin(admin.ModelAdmin):
	list_display = ("id", "user", "payment", "amount", "role", "status", "created_at")
	list_filter = ("status", "role")
	search_fields = ("user__email", "payment__provider_reference")

