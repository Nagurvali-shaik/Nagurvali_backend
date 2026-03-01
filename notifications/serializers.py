from rest_framework import serializers

from .models import DeviceToken, Notification


class DeviceTokenSerializer(serializers.Serializer):
    token = serializers.CharField()
    device_type = serializers.ChoiceField(choices=DeviceToken.DeviceType.choices)

    def create_or_update(self, user):
        token = self.validated_data["token"].strip()
        device_type = self.validated_data["device_type"]
        if not token:
            raise serializers.ValidationError({"token": "token is required"})
        device_token, _ = DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                "user": user,
                "device_type": device_type,
                "is_active": True,
            },
        )
        return device_token


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "type", "title", "message", "payload", "is_read", "created_at"]
