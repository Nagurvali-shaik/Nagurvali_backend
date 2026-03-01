# payments/models.py

import uuid
from django.db import models
from django.conf import settings
from order.models import Order


class Payment(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="payments"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="ETB")

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    provider = models.CharField(max_length=50)  # e.g. SANTIMPAY
    provider_reference = models.CharField(
        max_length=150,
        blank=True,
        null=True
    )

    is_verified = models.BooleanField(default=False)

    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["provider_reference"]),
        ]

    def __str__(self):
        return f"{self.order.id} - {self.status}"

class Refund(models.Model):

    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        APPROVED = "APPROVED", "Approved"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="refunds"
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    reason = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED
    )

    provider_reference = models.CharField(
        max_length=150,
        blank=True,
        null=True
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )

    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Refund {self.id} - {self.status}"


class WebhookLog(models.Model):

    provider = models.CharField(max_length=50)
    event_type = models.CharField(max_length=100)

    reference = models.CharField(max_length=150)
    payload = models.JSONField()

    processed = models.BooleanField(default=False)
    processing_attempts = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["reference"]),
            models.Index(fields=["processed"]),
        ]

class LedgerEntry(models.Model):

    class EntryType(models.TextChoices):
        PAYMENT = "PAYMENT", "Payment"
        COMMISSION = "COMMISSION", "Commission"
        VENDOR_PAYOUT = "VENDOR_PAYOUT", "Vendor Payout"
        REFUND = "REFUND", "Refund"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="ledger_entries"
    )

    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    entry_type = models.CharField(
        max_length=30,
        choices=EntryType.choices
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.entry_type} - {self.amount}"


class PayoutRequest(models.Model):

    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payout_requests")
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, related_name="payout_requests", null=True, blank=True)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, related_name="payout_requests", null=True, blank=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)

    payout_method = models.CharField(max_length=30, blank=True)
    payout_account = models.CharField(max_length=150, blank=True)
    provider_reference = models.CharField(max_length=150, blank=True, null=True)

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["provider_reference"]),
        ]


class Earning(models.Model):

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        PAID_OUT = "PAID_OUT", "Paid Out"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="earnings")
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="earnings")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="earnings")
    payout_request = models.ForeignKey(
        PayoutRequest,
        on_delete=models.SET_NULL,
        related_name="earning_items",
        null=True,
        blank=True,
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    role = models.CharField(max_length=30, blank=True)
    merchant_id_snapshot = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "payment")
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["merchant_id_snapshot"]),
        ]
