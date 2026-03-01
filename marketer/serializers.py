from decimal import Decimal
from rest_framework import serializers

from catalog.models import Product
from order.models import Order
from shop.models import Shop
from account.models import User
from .models import MarketerContract, MarketerContractProduct, MarketerCommission


class MarketerContractProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketerContractProduct
        fields = ["product"]


class MarketerContractSerializer(serializers.ModelSerializer):
    product_ids = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        write_only=True,
        many=True,
        required=False,
    )
    products = serializers.SerializerMethodField(read_only=True)
    shop_id = serializers.PrimaryKeyRelatedField(
        queryset=Shop.objects.all(),
        source="shop",
        write_only=True,
    )
    marketer_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role="MARKETER"),
        source="marketer",
        write_only=True,
    )

    class Meta:
        model = MarketerContract
        fields = [
            "id",
            "shop_id",
            "marketer_id",
            "commission_rate",
            "start_date",
            "end_date",
            "status",
            "products",
            "product_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def get_products(self, obj):
        return [
            {"id": str(cp.product_id), "name": cp.product.name}
            for cp in obj.contract_products.select_related("product").all()
        ]

    def validate(self, attrs):
        commission_rate = attrs.get("commission_rate")
        if commission_rate is not None and Decimal(str(commission_rate)) < Decimal("0"):
            raise serializers.ValidationError("commission_rate must be >= 0")
        return attrs

    def create(self, validated_data):
        product_ids = validated_data.pop("product_ids", [])
        request = self.context["request"]
        validated_data["created_by"] = request.user
        contract = MarketerContract.objects.create(**validated_data)
        if product_ids:
            for product in product_ids:
                if product.shop_id != contract.shop_id:
                    raise serializers.ValidationError("All products must belong to the contract shop")
            MarketerContractProduct.objects.bulk_create(
                [MarketerContractProduct(contract=contract, product=p) for p in product_ids]
            )
        return contract


class MarketerContractUpdateSerializer(serializers.ModelSerializer):
    product_ids = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        write_only=True,
        many=True,
        required=False,
    )

    class Meta:
        model = MarketerContract
        fields = ["commission_rate", "start_date", "end_date", "product_ids"]

    def update(self, instance, validated_data):
        product_ids = validated_data.pop("product_ids", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save(update_fields=["commission_rate", "start_date", "end_date", "updated_at"])
        if product_ids is not None:
            for product in product_ids:
                if product.shop_id != instance.shop_id:
                    raise serializers.ValidationError("All products must belong to the contract shop")
            MarketerContractProduct.objects.filter(contract=instance).delete()
            MarketerContractProduct.objects.bulk_create(
                [MarketerContractProduct(contract=instance, product=p) for p in product_ids]
            )
        return instance


class MarketerCommissionSerializer(serializers.ModelSerializer):
    order_id = serializers.PrimaryKeyRelatedField(source="order", read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(source="product", read_only=True)
    contract_id = serializers.PrimaryKeyRelatedField(source="contract", read_only=True)

    class Meta:
        model = MarketerCommission
        fields = [
            "id",
            "contract_id",
            "order_id",
            "product_id",
            "rate",
            "amount",
            "status",
            "created_at",
            "approved_at",
        ]


class MarketerDashboardSerializer(serializers.Serializer):
    total_earnings = serializers.DecimalField(max_digits=14, decimal_places=2)
    pending_commissions = serializers.DecimalField(max_digits=14, decimal_places=2)
    this_month_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_orders_influenced = serializers.IntegerField()
    total_units_sold = serializers.IntegerField()
    active_contracts = serializers.IntegerField()
    cards = serializers.ListField(child=serializers.DictField())
