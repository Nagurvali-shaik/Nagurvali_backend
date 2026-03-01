# payments/views/webhook.py
import json
import logging
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser

from .serializers import (
    PayoutCreateSerializer,
    PayoutRequestSerializer,
    RefundSerializer,
    RefundRequestSerializer,
)
from django.shortcuts import get_object_or_404

from courier.services import create_shipment_for_order, LogisticsError
from order.models import Order
from payment.models import Earning, Payment, PayoutRequest, Refund, WebhookLog
from payment.services.service import (
    PaymentConfigurationError,
    PaymentGatewayError,
    PaymentService,
    PaymentServiceError,
)
from marketer.services import MarketerCommissionService
from notifications.services import NotificationService, NotificationTemplates


def _get_order_merchant_id(order: Order) -> str:
    owner = getattr(getattr(order, "shop", None), "owner", None)
    merchant_id = getattr(owner, "merchant_id", None)
    if not merchant_id:
        raise PaymentServiceError("Shop owner merchant_id is required for payment")
    return merchant_id


class DirectPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("order_id")
        payment_method = request.data.get("payment_method")
        phone_number = request.data.get("phone_number")
        notify_url = request.data.get("notify_url")

        if not order_id or not payment_method or not phone_number:
            return Response(
                {
                    "detail": "order_id, payment_method and phone_number are required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        order = Order.objects.filter(id=order_id, user=request.user).select_related("shop__owner").first()
        if not order:
            return Response(
                {"detail": "Order not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if order.status != Order.Status.PENDING:
            return Response(
                {"detail": f"Order cannot be paid in status '{order.status}'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            merchant_id = _get_order_merchant_id(order)
            service = PaymentService(merchant_id=merchant_id)
            tx_id = order.payment_reference or str(order.id)
            provider_response = service.direct_payment(
                amount=order.total_amount,
                payment_reason=f"Order payment {order.order_number}",
                notify_url=notify_url,
                phone_number=phone_number,
                payment_method=payment_method,
                tx_id=tx_id,
            )
        except PaymentConfigurationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except PaymentServiceError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PaymentGatewayError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception:
            logger.exception("Unexpected direct payment error for order=%s", order.id)
            return Response(
                {"detail": "Unexpected payment error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        payment, _ = Payment.objects.update_or_create(
            order=order,
            user=request.user,
            provider="SANTIMPAY",
            defaults={
                "amount": order.total_amount,
                "status": Payment.Status.PROCESSING,
                "provider_reference": tx_id,
                "metadata": {
                    "merchant_id": merchant_id,
                    "provider_response": provider_response,
                },
            },
        )

        if order.payment_reference != tx_id:
            order.payment_reference = tx_id
            order.save(update_fields=["payment_reference", "updated_at"])

        return Response(
            {
                "message": "Direct payment initiated",
                "order_id": str(order.id),
                "transaction_id": tx_id,
                "payment_id": str(payment.id),
                "provider_response": provider_response,
            },
            status=status.HTTP_200_OK,
        )


class RefundListCreateView(APIView):
    """List refunds for the requesting user (staff see all) and allow creating refund requests."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.is_staff:
            qs = Refund.objects.select_related("payment", "requested_by").all().order_by("-created_at")
        else:
            qs = Refund.objects.select_related("payment").filter(requested_by=request.user).order_by("-created_at")
        serializer = RefundSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = RefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = serializer.validated_data["payment"]
        amount = serializer.validated_data["amount"]
        reason = serializer.validated_data.get("reason", "")

        # Only allow requesting refunds for own payments unless staff
        if not request.user.is_staff and payment.user != request.user:
            return Response({"detail": "Cannot request refund for this payment"}, status=status.HTTP_403_FORBIDDEN)

        refund = Refund.objects.create(
            payment=payment,
            amount=amount,
            reason=reason,
            status=Refund.Status.REQUESTED,
            requested_by=request.user,
        )
        return Response(RefundSerializer(refund).data, status=status.HTTP_201_CREATED)


class RefundApproveView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        refund = get_object_or_404(Refund, pk=pk)
        if refund.status != Refund.Status.REQUESTED:
            return Response({"detail": "Only requested refunds can be approved"}, status=status.HTTP_400_BAD_REQUEST)
        refund.status = Refund.Status.APPROVED
        refund.save(update_fields=["status", "updated_at"])
        return Response(RefundSerializer(refund).data)


class RefundExecuteView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        refund = get_object_or_404(
            Refund.objects.select_related("payment", "payment__order__shop__owner", "requested_by"),
            pk=pk,
        )
        if refund.status != Refund.Status.APPROVED:
            return Response({"detail": "Only approved refunds can be executed"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            merchant_id = _get_order_merchant_id(refund.payment.order)
            service = PaymentService(merchant_id=merchant_id)
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
            return Response(RefundSerializer(refund).data)
        except PaymentServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PayoutRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PayoutCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        has_available = Earning.objects.filter(user=request.user, status=Earning.Status.AVAILABLE).exists()
        if not has_available:
            return Response({"detail": "No available earnings to payout"}, status=status.HTTP_400_BAD_REQUEST)
        merchant_id = request.user.merchant_id or getattr(settings, "PLATFORM_MERCHANT_ID", "")
        try:
            service = PaymentService(merchant_id=merchant_id)
            payout_request = service.request_total_user_payout(user=request.user)
        except PaymentServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PaymentGatewayError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(PayoutRequestSerializer(payout_request).data, status=status.HTTP_201_CREATED)


class PayoutHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.is_staff:
            queryset = PayoutRequest.objects.select_related("payment", "order", "user").all().order_by("-created_at")
        else:
            queryset = PayoutRequest.objects.select_related("payment", "order").filter(user=request.user).order_by("-created_at")
        data = PayoutRequestSerializer(queryset, many=True).data
        summary_qs = Earning.objects.filter(user=request.user, status=Earning.Status.AVAILABLE) if not request.user.is_staff else Earning.objects.filter(status=Earning.Status.AVAILABLE)
        available_total = sum((e.amount for e in summary_qs), Decimal("0.00"))
        return Response(
            {
                "available_earnings": str(available_total),
                "history": data,
            }
        )




logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name="dispatch")
class SantimPayWebhookView(View):
    """
    Endpoint to receive SantimPay webhook notifications.
    Handles both Payments and Refunds.
    """

    def get(self, request: HttpRequest):
        # Simple GET for sanity checks
        return JsonResponse({"info": "SantimPay Webhook endpoint, POST only"})

    def post(self, request: HttpRequest):
        webhook_log = None

        # Parse JSON
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            logger.error("SantimPay webhook invalid JSON: %s", request.body)
            WebhookLog.objects.create(
                provider="SANTIMPAY",
                event_type="INVALID_JSON",
                reference="INVALID_JSON",
                payload={"raw_body": request.body.decode("utf-8", errors="replace")},
                processed=False,
                processing_attempts=1,
            )
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        logger.info("SantimPay webhook received: %s", payload)

        # Extract transaction ID
        tx_id = payload.get("id")
        if not tx_id:
            logger.warning("SantimPay webhook missing transaction ID")
            WebhookLog.objects.create(
                provider="SANTIMPAY",
                event_type="MISSING_TX_ID",
                reference="MISSING_TX_ID",
                payload=payload,
                processed=False,
                processing_attempts=1,
            )
            return JsonResponse({"error": "Missing transaction ID"}, status=400)

        webhook_log = WebhookLog.objects.create(
            provider="SANTIMPAY",
            event_type="RECEIVED",
            reference=tx_id,
            payload=payload,
            processed=False,
            processing_attempts=1,
        )

        # Try to sync Payment first
        payment = Payment.objects.filter(provider_reference=tx_id).select_related("order__shop__owner").first()
        if payment:
            try:
                webhook_log.event_type = "PAYMENT_SYNC"
                merchant_id = (payment.metadata or {}).get("merchant_id") or _get_order_merchant_id(payment.order)
                service = PaymentService(merchant_id=merchant_id)
                with transaction.atomic():
                    order = payment.order
                    previous_order_status = order.status
                    service.sync_order_status(order, tx_id=tx_id)
                    order.refresh_from_db(fields=["status"])
                    payment.refresh_from_db(fields=["status", "metadata"])

                    if previous_order_status != Order.Status.PAID and order.status == Order.Status.PAID:
                        created_commissions = MarketerCommissionService.create_pending_for_order(order)
                        try:
                            title, message, payload = NotificationTemplates.payment_success(order)
                            NotificationService.notify(
                                user=order.user,
                                notification_type="payment_success",
                                title=title,
                                message=message,
                                payload=payload,
                            )
                        except Exception:
                            logger.exception("Failed to send payment_success notification order=%s", order.id)
                        try:
                            title, message, payload = NotificationTemplates.payment_confirmed(order)
                            NotificationService.notify(
                                user=order.shop.owner,
                                notification_type="payment_confirmed",
                                title=title,
                                message=message,
                                payload=payload,
                            )
                        except Exception:
                            logger.exception("Failed to send payment_confirmed notification order=%s", order.id)
                        try:
                            for item in order.items.select_related("product__supplier", "variant__product__supplier").all():
                                product = item.product if item.product else (item.variant.product if item.variant else None)
                                supplier = getattr(product, "supplier", None) if product else None
                                if not supplier:
                                    continue
                                title, message, payload = NotificationTemplates.product_sold(order, product)
                                NotificationService.notify(
                                    user=supplier,
                                    notification_type="product_sold",
                                    title=title,
                                    message=message,
                                    payload=payload,
                                )
                        except Exception:
                            logger.exception("Failed to send supplier product_sold notifications order=%s", order.id)
                        try:
                            for commission in created_commissions:
                                title, message, payload = NotificationTemplates.commission_created(order, commission)
                                NotificationService.notify(
                                    user=commission.contract.marketer,
                                    notification_type="commission_created",
                                    title=title,
                                    message=message,
                                    payload=payload,
                                )
                        except Exception:
                            logger.exception("Failed to send commission_created notifications order=%s", order.id)
                        if order.delivery_method == Order.DeliveryMethod.COURIER:
                            try:
                                create_shipment_for_order(order)
                            except LogisticsError:
                                logger.exception("Shipment creation failed for order=%s", order.id)
                webhook_log.processed = True
                webhook_log.save(update_fields=["event_type", "processed"])
                logger.info("Payment synced successfully: tx_id=%s", tx_id)
            except PaymentGatewayError as e:
                webhook_log.event_type = "PAYMENT_SYNC_FAILED"
                webhook_log.save(update_fields=["event_type"])
                logger.exception("Gateway error while syncing payment tx_id=%s: %s", tx_id, str(e))
                return JsonResponse({"error": str(e)}, status=502)
            except PaymentServiceError as e:
                webhook_log.event_type = "PAYMENT_SYNC_FAILED"
                webhook_log.save(update_fields=["event_type"])
                logger.exception("Payment sync failed for tx_id=%s: %s", tx_id, str(e))
                return JsonResponse({"error": str(e)}, status=400)
            except Exception as e:
                webhook_log.event_type = "PAYMENT_SYNC_FAILED"
                webhook_log.save(update_fields=["event_type"])
                logger.exception("Stock update failed for payment tx_id=%s: %s", tx_id, str(e))
                return JsonResponse({"error": str(e)}, status=409)
            return JsonResponse({"status": "payment synced"}, status=200)

        # Try to sync Refund
        refund = Refund.objects.filter(provider_reference=tx_id).select_related("payment__order__shop__owner").first()
        if refund:
            try:
                webhook_log.event_type = "REFUND_SYNC"
                merchant_id = (refund.payment.metadata or {}).get("merchant_id") or _get_order_merchant_id(refund.payment.order)
                service = PaymentService(merchant_id=merchant_id)
                with transaction.atomic():
                    service.sync_refund_status(refund)
                webhook_log.processed = True
                webhook_log.save(update_fields=["event_type", "processed"])
                logger.info("Refund synced successfully: tx_id=%s", tx_id)
            except PaymentGatewayError as e:
                webhook_log.event_type = "REFUND_SYNC_FAILED"
                webhook_log.save(update_fields=["event_type"])
                logger.exception("Gateway error while syncing refund tx_id=%s: %s", tx_id, str(e))
                return JsonResponse({"error": str(e)}, status=502)
            except PaymentServiceError as e:
                webhook_log.event_type = "REFUND_SYNC_FAILED"
                webhook_log.save(update_fields=["event_type"])
                logger.exception("Refund sync failed for tx_id=%s: %s", tx_id, str(e))
                return JsonResponse({"error": str(e)}, status=400)
            except Exception:
                webhook_log.event_type = "REFUND_SYNC_FAILED"
                webhook_log.save(update_fields=["event_type"])
                logger.exception("Unexpected error syncing refund tx_id=%s", tx_id)
                return JsonResponse({"error": "Unexpected refund sync error"}, status=500)
            return JsonResponse({"status": "refund synced"}, status=200)

        # Transaction not found
        webhook_log.event_type = "NOT_FOUND"
        webhook_log.save(update_fields=["event_type"])
        logger.warning("SantimPay webhook transaction not found: tx_id=%s", tx_id)
        return JsonResponse({"error": "Transaction not found"}, status=404)
