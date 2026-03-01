from django.urls import path
from .views import *
urlpatterns = [
    path('', ShopListCreateView.as_view(), name='shop-list-create'),
    path('shops/<uuid:pk>/', ShopDetailView.as_view(), name='shop-detail'),
    path('themes/', CreateThemeView.as_view(), name='create-theme'),
    path('theme-settings/', CreateThemeSettingsView.as_view(), name='create-theme-settings'),
]
