from django.urls import path

from .views import CourierWebhookView, ShipmentDetailView


urlpatterns = [
    path("webhook/<str:courier>/", CourierWebhookView.as_view(), name="courier-webhook"),
    path("shipments/<uuid:pk>/", ShipmentDetailView.as_view(), name="shipment-detail"),
]

