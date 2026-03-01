

from rest_framework import serializers


class CartItemCreateSerializer(serializers.Serializer):
    shop_id = serializers.UUIDField()
    product_id = serializers.UUIDField()
    variant_id = serializers.UUIDField(required=False, allow_null=True)
    marketer_contract_id = serializers.UUIDField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1)
