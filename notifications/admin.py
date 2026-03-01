from django.contrib import admin

from .models import DeviceToken, Notification


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "device_type", "is_active", "created_at")
    search_fields = ("token", "user__email")
    list_filter = ("device_type", "is_active")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "type", "is_read", "created_at")
    search_fields = ("user__email", "title", "message")
    list_filter = ("type", "is_read")

# Register your models here.
