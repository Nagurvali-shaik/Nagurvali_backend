from rest_framework import serializers

from .models import Earning, Refund, Payment, PayoutRequest


class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = ["id", "payment", "amount", "reason", "status", "provider_reference", "metadata", "requested_by", "created_at", "updated_at"]


class RefundRequestSerializer(serializers.Serializer):
    payment_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason = serializers.CharField(allow_blank=True, required=False)

    def validate(self, attrs):
        from django.db import models as dj_models

        payment_id = attrs.get("payment_id")
        amount = attrs.get("amount")

        payment = Payment.objects.filter(id=payment_id).select_related("order", "user").first()
        if not payment:
            raise serializers.ValidationError("Payment not found")
        if payment.status != Payment.Status.COMPLETED:
            raise serializers.ValidationError("Only completed payments can be refunded")

        total_refunded = (
            Refund.objects.filter(payment=payment, status=Refund.Status.COMPLETED)
            .aggregate(total=dj_models.Sum("amount"))["total"] or 0
        )
        if total_refunded + amount > payment.amount:
            raise serializers.ValidationError("Refund amount exceeds remaining refundable amount")

        attrs["payment"] = payment
        return attrs


class PayoutRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutRequest
        fields = [
            "id",
            "user",
            "payment",
            "order",
            "amount",
            "status",
            "payout_method",
            "payout_account",
            "provider_reference",
            "metadata",
            "created_at",
            "updated_at",
        ]


class PayoutCreateSerializer(serializers.Serializer):
    confirm = serializers.BooleanField(default=True)

    def validate(self, attrs):
        if attrs.get("confirm") is not True:
            raise serializers.ValidationError("confirm must be true")
        return attrs


class EarningSerializer(serializers.ModelSerializer):
    class Meta:
        model = Earning
        fields = [
            "id",
            "user",
            "payment",
            "order",
            "payout_request",
            "amount",
            "role",
            "merchant_id_snapshot",
            "status",
            "metadata",
            "created_at",
            "updated_at",
        ]
