import uuid
from django.conf import settings
from django.db import models


class DeviceToken(models.Model):
    class DeviceType(models.TextChoices):
        WEB = "web", "Web"
        ANDROID = "android", "Android"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="device_tokens")
    token = models.TextField(unique=True)
    device_type = models.CharField(max_length=20, choices=DeviceType.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["device_type"]),
        ]


class Notification(models.Model):
    class Type(models.TextChoices):
        PAYMENT_SUCCESS = "payment_success", "Payment Success"
        ORDER_SHIPPED = "order_shipped", "Order Shipped"
        ORDER_DELIVERED = "order_delivered", "Order Delivered"
        NEW_ORDER = "new_order", "New Order"
        PAYMENT_CONFIRMED = "payment_confirmed", "Payment Confirmed"
        PRODUCT_SOLD = "product_sold", "Product Sold"
        COMMISSION_CREATED = "commission_created", "Commission Created"
        COMMISSION_APPROVED = "commission_approved", "Commission Approved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=50, choices=Type.choices)
    title = models.CharField(max_length=255)
    message = models.TextField()
    payload = models.JSONField(default=dict)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["type"]),
            models.Index(fields=["created_at"]),
        ]

# Create your models here.
