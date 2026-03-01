from django.db import models
from catalog.models import ProductVariant
# Create your models here.
class Location(models.Model):
    name = models.CharField(max_length=255)  # warehouse or supplier
    type = models.CharField(max_length=50, choices=[("WAREHOUSE","Warehouse"),("SUPPLIER","Supplier")])
    contact = models.JSONField(blank=True, null=True)

class Inventory(models.Model):
    variant = models.ForeignKey(ProductVariant, related_name="inventory", on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    quantity_available = models.PositiveIntegerField(default=0)
    quantity_reserved = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

class StockMovement(models.Model):
    inventory = models.ForeignKey(Inventory, related_name="movements", on_delete=models.CASCADE)
    quantity = models.IntegerField()  # positive for stock_in, negative for stock_out
    reason = models.CharField(max_length=255)  # "Order Reserved", "Stock Adjustment"
    created_at = models.DateTimeField(auto_now_add=True)
