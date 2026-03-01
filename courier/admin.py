from django.contrib import admin

from .models import CourierPartner, Shipment


@admin.register(CourierPartner)
class CourierPartnerAdmin(admin.ModelAdmin):
    list_display = ("name", "provider_code", "is_active", "priority", "created_at")
    list_filter = ("is_active", "provider_code")
    search_fields = ("name", "provider_code")


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "courier", "status", "external_tracking_id", "updated_at")
    list_filter = ("status", "courier")
    search_fields = ("order__order_number", "external_tracking_id", "external_shipment_id")
