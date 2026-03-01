from rest_framework.serializers import ModelSerializer
from django.contrib.auth import get_user_model
from .models import *
from rest_framework import serializers
from .badge_logic import resolve_badge
User = get_user_model()

class MerchantIdRepresentationMixin:
    def to_representation(self, instance):
        resolve_badge(instance, persist=True)
        data = super().to_representation(instance)
        if "merchant_id" in data:
            data["merchant_id"] = instance.get_decoded_merchant_id()
        return data


class UserSerializer(MerchantIdRepresentationMixin, ModelSerializer):
    class Meta:
        model = User
        fields = ['id','first_name', 'last_name', 'email', 'merchant_id', 'phone_number', 'location', 'badge', 'created_at', 'updated_at',  'password']
        extra_kwargs = {
            'password': {'write_only': True},}
        read_only_fields = ('id', 'created_at', 'updated_at')        
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = super().create(validated_data)
        if password:
            user.set_password(password)
            role = validated_data.get('role', 'CUSTOMER')
            user.role = role
            status = validated_data.get('status', 'new')
            user.status = status
            user.save()
        return user
    
class ShopOwnerSerializer(MerchantIdRepresentationMixin, ModelSerializer):
    class Meta:
        model = User
        fields = ['id','first_name', 'last_name', 'email', 'merchant_id', 'phone_number', 'created_at', 'updated_at', 'badge',  'avatar', 'license_document', 'password']
        extra_kwargs = {
            'password': {'write_only': True},}
        read_only_fields = ('id', 'created_at', 'updated_at')        
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = super().create(validated_data)
        if password:
            user.set_password(password)
            role = 'SHOP_OWNER'
            user.role = role
            user.save()
        return user

class SupplierSerializer(MerchantIdRepresentationMixin, ModelSerializer):
    class Meta:
        model = User
        fields = ['id','company_name',  'email', 'merchant_id', 'phone_number', 'location', 'created_at', 'updated_at', 'badge',  'avatar', 'license_document', 'policy', 'password', 'bank_account', 'bank_account_number']
        extra_kwargs = {
            'password': {'write_only': True},}
        read_only_fields = ('id', 'created_at', 'updated_at')        
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = super().create(validated_data)
        if password:
            user.set_password(password)
            role = 'SUPPLIER'
            user.role = role
            user.save()
        return user
class CourierSerializer(MerchantIdRepresentationMixin, ModelSerializer):
    class Meta:
        model = User
        fields = ['id','company_name', 'email', 'merchant_id', 'phone_number', 'location', 'created_at', 'updated_at', 'badge',  'avatar', 'license_document', 'is_available', 'password']
        extra_kwargs = {
            'password': {'write_only': True},}
        read_only_fields = ('id', 'created_at', 'updated_at')        
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = super().create(validated_data)
        if password:
            user.set_password(password)
            role = 'COURIER'
            user.role = role
            user.save()
        return user



class PaymentMethodSerializer(ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ["payment_type", "account_number", "phone_number"]

    def validate(self, attrs):
        payment_type = attrs.get("payment_type")
        account_number = attrs.get("account_number")
        phone_number = attrs.get("phone_number")

        if payment_type == "BANK" and not account_number:
            raise serializers.ValidationError({"account_number": "Bank account number is required."})
        elif payment_type in ["TELEBIRR", "MPESA"] and not phone_number:
            raise serializers.ValidationError({"phone_number": "Phone number is required for this payment type."})
        
        return attrs
    def create(self, validated_data):
        # Always assign the shop_owner from the logged-in user
        user = self.context['request'].user

        # Check that the user is really a ShopOwner
        if user.role != "SHOP_OWNER":
            raise serializers.ValidationError("Only shop owners can add payment methods.")

        validated_data['shop_owner'] = user
        return super().create(validated_data)


class MarketerSerializer(MerchantIdRepresentationMixin, ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'first_name',
            'last_name',
            'company_name',
            'avatar',
            'email',
            'merchant_id',
            'phone_number',
            'bio',
            'base_price',
            'marketer_commission',
            'followers_count',
            'instagram',
            'marketer_type',
            'pricing_type',
            'rating',
            'badge',
            'services',
            'team_size',
            'tiktok',
            'total_jobs',
            'website',
            'youtube',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ('id', 'created_at', 'updated_at')
