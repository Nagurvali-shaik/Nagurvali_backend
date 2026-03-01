from decimal import Decimal

from rest_framework import serializers

from catalog.models import Category, Product, ProductMedia, ProductVariant


class SupplierProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ["id", "variant_name", "price", "attributes", "stock", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class SupplierProductMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductMedia
        fields = ["id", "media_type", "file", "caption", "is_primary", "order"]
        read_only_fields = ["id"]


class SupplierProductSerializer(serializers.ModelSerializer):
    variants = SupplierProductVariantSerializer(many=True, required=False)
    media = SupplierProductMediaSerializer(many=True, required=False)
    stock = serializers.IntegerField(write_only=True, required=False, min_value=0)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source="category",
        write_only=True,
        required=False,
        allow_null=True,
    )
    category = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "sku",
            "price",
            "supplier_price",
            "minimum_wholesale_quantity",
            "shop_owner_price",
            "category_id",
            "category",
            "is_active",
            "weight",
            "dimensions",
            "tags",
            "variants",
            "media",
            "stock",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_minimum_wholesale_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("minimum_wholesale_quantity must be at least 1.")
        return value

    def validate_supplier_price(self, value):
        if value is not None and Decimal(value) <= Decimal("0"):
            raise serializers.ValidationError("supplier_price must be greater than 0.")
        return value

    def get_category(self, obj):
        if not obj.category:
            return None
        return {
            "id": str(obj.category.id),
            "name": obj.category.name,
            "slug": obj.category.slug,
        }

    def create(self, validated_data):
        variants_data = validated_data.pop("variants", [])
        media_data = validated_data.pop("media", [])
        default_stock = validated_data.pop("stock", None)
        request = self.context["request"]
        product = Product.objects.create(
            supplier=request.user,
            shop=None,
            **validated_data,
        )
        for variant_data in variants_data:
            if default_stock is not None and variant_data.get("stock") is None:
                variant_data["stock"] = default_stock
            ProductVariant.objects.create(product=product, **variant_data)
        if not variants_data:
            ProductVariant.objects.create(
                product=product,
                variant_name="Default",
                price=product.price,
                stock=default_stock if default_stock is not None else 1,
            )
        for media_data_item in media_data:
            ProductMedia.objects.create(product=product, **media_data_item)
        return product


class SupplierStockUpdateSerializer(serializers.Serializer):
    stock = serializers.IntegerField(min_value=0)


class SupplierDashboardSerializer(serializers.Serializer):
    total_earnings = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_units_sold = serializers.IntegerField()
    orders_supplied = serializers.IntegerField()
    pending_payout = serializers.DecimalField(max_digits=14, decimal_places=2)
    this_month_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    cards = serializers.ListField(child=serializers.DictField())
