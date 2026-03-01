from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import *

urlpatterns = [
    path("register/", RegisterUserView.as_view(), name="register"),
    path("login/", TokenObtainPairView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("user/<int:pk>/", UserDetailView.as_view(), name="user-detail"),
    path("register-shop-owner/", RegisterShopOwnerView.as_view(), name="register-shop-owner"),
    path("register-supplier/", RegisterSupplierView.as_view(), name="register-supplier"),
    path("register-courier/", RegisterCourierView.as_view(), name="register-courier"),
    path('create-payment-method/', CreatePaymentMethodView.as_view(), name="create-payment-method"),
    path("register-marketer/", RegisterMarketerView.as_view(), name="register-marketer"),

    
]
