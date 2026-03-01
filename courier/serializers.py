from rest_framework import serializers

from .models import Shipment


class ShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = [
            "id",
            "order",
            "courier",
            "status",
            "external_shipment_id",
            "external_tracking_id",
            "last_event",
            "last_payload",
            "metadata",
            "created_at",
            "updated_at",
        ]
