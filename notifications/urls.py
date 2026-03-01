from django.urls import path

from .views import (
    DeviceTokenView,
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationReadView,
)


urlpatterns = [
    path("", NotificationListView.as_view(), name="notifications-list"),
    path("device-token/", DeviceTokenView.as_view(), name="notifications-device-token"),
    path("<uuid:pk>/read/", NotificationReadView.as_view(), name="notifications-read-one"),
    path("mark-all-read/", NotificationMarkAllReadView.as_view(), name="notifications-read-all"),
]
