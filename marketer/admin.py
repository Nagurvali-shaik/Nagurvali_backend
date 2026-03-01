from django.contrib import admin

from .models import MarketerContract, MarketerContractProduct, MarketerCommission


@admin.register(MarketerContract)
class MarketerContractAdmin(admin.ModelAdmin):
    list_display = ("id", "shop", "marketer", "status", "commission_rate", "start_date", "end_date")
    search_fields = ("id", "shop__name", "marketer__email")
    list_filter = ("status",)


@admin.register(MarketerContractProduct)
class MarketerContractProductAdmin(admin.ModelAdmin):
    list_display = ("id", "contract", "product")


@admin.register(MarketerCommission)
class MarketerCommissionAdmin(admin.ModelAdmin):
    list_display = ("id", "contract", "order", "product", "amount", "status")
    list_filter = ("status",)

# Register your models here.
