from .models import *
from django.contrib.auth import get_user_model
from rest_framework import serializers
from account.serializers import MarketerSerializer
User = get_user_model()

class ThemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Theme
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "preview_image",
            "version",
            "is_active",
        ]

class ShopThemeSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopThemeSettings
        fields = [
            "primary_color",
            "secondary_color",
            "logo",
            "banner_image",
            "font_family",
        ]
class ShopSerializer(serializers.ModelSerializer):

    theme = ThemeSerializer(read_only=True)

    theme_id = serializers.PrimaryKeyRelatedField(
        queryset=Theme.objects.all(),
        source="theme",
        write_only=True,
        required=False
    )

    theme_settings = ShopThemeSettingsSerializer(read_only=True)

    marketer = MarketerSerializer(read_only=True, many=True)

    marketer_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='MARKETER'),
        source="marketer",  # 🔥 THIS IS IMPORTANT
        write_only=True,
        many=True,
        required=False
    )

    class Meta:
        model = Shop
        fields = [
            "id",
            "name",
            "description",
            "domain",
            "created_at",
            "marketer",
            "marketer_ids",
            "theme",
            "theme_id",
            "theme_settings",
        ]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        request = self.context["request"]

        # Remove marketers before create
        marketers = validated_data.pop("marketer", [])

        shop = Shop.objects.create(
            owner=request.user,
            **validated_data
        )

        # Assign ManyToMany AFTER creation
        if marketers:
            shop.marketer.set(marketers)

        ShopThemeSettings.objects.create(shop=shop)

        return shop
