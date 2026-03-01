import uuid
from django.db import models

from order.models import Order


class CourierPartner(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    provider_code = models.CharField(max_length=50, unique=True)  # e.g. hudhud
    api_base_url = models.URLField(blank=True)
    api_key = models.CharField(max_length=255, blank=True)
    webhook_secret = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=100)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "name"]

    def __str__(self):
        return f"{self.name} ({self.provider_code})"


class Shipment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CREATED = "CREATED", "Created"
        PICKED_UP = "PICKED_UP", "Picked Up"
        IN_TRANSIT = "IN_TRANSIT", "In Transit"
        OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY", "Out for Delivery"
        DELIVERED = "DELIVERED", "Delivered"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(Order, related_name="shipment", on_delete=models.CASCADE)
    courier = models.ForeignKey(CourierPartner, related_name="shipments", on_delete=models.PROTECT)

    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    external_shipment_id = models.CharField(max_length=150, blank=True)
    external_tracking_id = models.CharField(max_length=150, blank=True, db_index=True)
    last_event = models.CharField(max_length=100, blank=True)
    last_payload = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["external_tracking_id"]),
        ]

    def __str__(self):
        return f"{self.order.order_number} - {self.status}"
