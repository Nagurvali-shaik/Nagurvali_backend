from django.urls import path

from .views import (
    SupplierDashboardView,
    SupplierLowStockAlertView,
    SupplierProductDetailView,
    SupplierProductListCreateView,
    SupplierProductMediaCreateView,
    SupplierProductVariantCreateView,
    SupplierVariantStockUpdateView,
)


urlpatterns = [
    path("dashboard/", SupplierDashboardView.as_view(), name="supplier-dashboard"),
    path("products/", SupplierProductListCreateView.as_view(), name="supplier-products"),
    path("products/<uuid:pk>/", SupplierProductDetailView.as_view(), name="supplier-product-detail"),
    path("products/<uuid:pk>/variants/", SupplierProductVariantCreateView.as_view(), name="supplier-product-variants"),
    path("products/<uuid:pk>/media/", SupplierProductMediaCreateView.as_view(), name="supplier-product-media"),
    path("variants/<uuid:pk>/stock/", SupplierVariantStockUpdateView.as_view(), name="supplier-variant-stock"),
    path("alerts/low-stock/", SupplierLowStockAlertView.as_view(), name="supplier-low-stock-alert"),
]

