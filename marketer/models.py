import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone

from shop.models import Shop
from catalog.models import Product
from order.models import Order, OrderItem


class MarketerContract(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACTIVE = "ACTIVE", "Active"
        PAUSED = "PAUSED", "Paused"
        ENDED = "ENDED", "Ended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="marketer_contracts")
    marketer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="marketer_contracts",
        limit_choices_to={"role": "MARKETER"},
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Commission percent, e.g. 10.00 means 10%",
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_marketer_contracts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["start_date", "end_date"]),
        ]
        unique_together = ("shop", "marketer")

    def __str__(self):
        return f"{self.shop_id} -> {self.marketer_id} ({self.status})"

    def is_active(self) -> bool:
        if self.status != self.Status.ACTIVE:
            return False
        today = timezone.localdate()
        if self.start_date and self.start_date > today:
            return False
        if self.end_date and self.end_date < today:
            return False
        return True


class MarketerContractProduct(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(MarketerContract, on_delete=models.CASCADE, related_name="contract_products")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="marketer_contracts")

    class Meta:
        unique_together = ("contract", "product")
        indexes = [
            models.Index(fields=["contract"]),
            models.Index(fields=["product"]),
        ]

    def __str__(self):
        return f"{self.contract_id} -> {self.product_id}"


class MarketerCommission(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(MarketerContract, on_delete=models.CASCADE, related_name="commissions")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="marketer_commissions")
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="marketer_commissions")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="marketer_commissions")

    rate = models.DecimalField(max_digits=5, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("contract", "order_item")
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["contract"]),
            models.Index(fields=["order"]),
        ]

    def __str__(self):
        return f"{self.order_id} - {self.amount} - {self.status}"

# Create your models here.
