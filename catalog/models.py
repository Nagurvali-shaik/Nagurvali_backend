from django.db import models
from shop.models import Shop
import uuid
from django.utils.text import slugify


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True, null=True)
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subcategories'
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            base_slug = slugify(self.name) or f"category-{uuid.uuid4().hex[:8]}"
            candidate = base_slug
            counter = 1
            while Category.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base_slug}-{counter}"
                counter += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name



  # link products to shops

class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="products", blank=True, null=True)
    supplier = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        related_name="supplied_products",
        blank=True,
        null=True,
        limit_choices_to={"role": "SUPPLIER"},
    )
    sku = models.CharField(max_length=100, unique=True, blank=True, null=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    supplier_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    minimum_wholesale_quantity = models.PositiveIntegerField(default=1)
    shop_owner_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name="products")
    is_active = models.BooleanField(default=True)
    weight = models.FloatField(blank=True, null=True)  # kg
    dimensions = models.JSONField(blank=True, null=True)  # {length, width, height} in cm
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tags = models.JSONField(blank=True, default=list)  # ["eco-friendly", "bestseller"]

    def save(self, *args, **kwargs):
        if not self.sku:
            base = slugify(self.name) if self.name else "product"
            base = (base or "product").upper().replace("-", "")
            base = base[:12] if base else "PRODUCT"
            candidate = f"{base}-{uuid.uuid4().hex[:6].upper()}"
            while Product.objects.filter(sku=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{uuid.uuid4().hex[:6].upper()}"
            self.sku = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class ProductMedia(models.Model):
    MEDIA_TYPE = [
        ("IMAGE", "Image"),
        ("VIDEO", "Video"),
        ("DOCUMENT", "Document"),
    ]
    product = models.ForeignKey(Product, related_name="media", on_delete=models.CASCADE)
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE)
    file = models.FileField(upload_to="products/media/")
    caption = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)  # main image
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.product.name} - {self.media_type}"

class ProductVariant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, related_name="variants", on_delete=models.CASCADE)
    variant_name = models.CharField(max_length=255)  # e.g., "Red / Large"
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    attributes = models.JSONField(blank=True, null=True)  # {"color": "red", "size": "L"}
    stock = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.product.name} - {self.variant_name}"


class ProductReview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, related_name="reviews", on_delete=models.CASCADE)
    user = models.ForeignKey("account.User", related_name="product_reviews", on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=120, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("product", "user")
        indexes = [
            models.Index(fields=["product", "created_at"]),
            models.Index(fields=["rating"]),
        ]

    def __str__(self):
        return f"{self.product_id} - {self.user_id} - {self.rating}"


#example 
# {
#   "name": "Premium T-Shirt",
#   "description": "A high-quality t-shirt made from organic cotton.",
#   "sku": "TSHIRT-002",
#   "price": "39.99",
#   "category": 1,
#   "is_active": true,
#   "weight": "0.35",
#   "dimensions": "32x22x3",
#   "tags": ["tshirt", "premium", "2026"],

#   "variants": [
#     {
#       "variant_name": "Red - Large",
#       "price": "39.99",
#       "attributes": {
#         "color": "Red",
#         "size": "L"
#       }
#     },
#     {
#       "variant_name": "Blue - Medium",
#       "price": "37.99",
#       "attributes": {
#         "color": "Blue",
#         "size": "M"
#       }
#     }
#   ],

#   "media": [
#     {
#       "media_type": "image",
#       "file": "products/images/tshirt1.jpg",
#       "caption": "Front view",
#       "is_primary": true,
#       "order": 1
#     },
#     {
#       "media_type": "image",
#       "file": "products/images/tshirt2.jpg",
#       "caption": "Back view",
#       "is_primary": false,
#       "order": 2
#     }
#   ]
# }
