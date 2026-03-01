from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions, status
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CourierPartner, Shipment
from .serializers import ShipmentSerializer
from .services import LogisticsError, process_courier_webhook


@method_decorator(csrf_exempt, name="dispatch")
class CourierWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, courier):
        payload = request.data if isinstance(request.data, dict) else {}
        partner = CourierPartner.objects.filter(provider_code__iexact=courier).first()
        if not partner:
            return Response({"detail": "Courier not configured"}, status=status.HTTP_404_NOT_FOUND)

        if partner.webhook_secret:
            incoming = request.headers.get("X-Webhook-Secret", "")
            if incoming != partner.webhook_secret:
                return Response({"detail": "Invalid webhook signature"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            shipment = process_courier_webhook(courier, payload)
            return Response(
                {
                    "message": "Webhook processed",
                    "shipment_id": str(shipment.id),
                    "status": shipment.status,
                    "order_status": shipment.order.status,
                },
                status=status.HTTP_200_OK,
            )
        except LogisticsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ShipmentDetailView(RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ShipmentSerializer
    queryset = Shipment.objects.select_related("order", "courier").all()
