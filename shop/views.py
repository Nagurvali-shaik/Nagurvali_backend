from rest_framework import permissions
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView

from .models import *
from .serializers import *

# Create your views here.

class ShopListCreateView(ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
class ShopDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer

class CreateThemeView(ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Theme.objects.all()
    serializer_class = ThemeSerializer
class CreateThemeSettingsView(ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = ShopThemeSettings.objects.all()
    serializer_class = ShopThemeSettingsSerializer
    