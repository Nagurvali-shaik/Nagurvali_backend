from rest_framework import permissions
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from .serializers import *
from .models import *
from django.contrib.auth import get_user_model

User = get_user_model()

class RegisterUserView(ListCreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = UserSerializer
class UserDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = User.objects.all()
    serializer_class = UserSerializer
class RegisterShopOwnerView(ListCreateAPIView):
    queryset = User.objects.filter(role='SHOP_OWNER')
    permission_classes = [permissions.AllowAny]
    serializer_class = ShopOwnerSerializer
class RegisterSupplierView(ListCreateAPIView):
    queryset = User.objects.filter(role='SUPPLIER')
    permission_classes = [permissions.AllowAny]
    serializer_class = SupplierSerializer
class RegisterCourierView(ListCreateAPIView):
    queryset = User.objects.filter(role='COURIER')
    permission_classes = [permissions.AllowAny]
    serializer_class = CourierSerializer
class CreatePaymentMethodView(ListCreateAPIView):
    queryset = PaymentMethod.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PaymentMethodSerializer
class RegisterMarketerView(ListCreateAPIView):
    queryset = User.objects.filter(role='MARKETER')
    permission_classes = [permissions.AllowAny]
    serializer_class = MarketerSerializer