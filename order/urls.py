from django.urls import path
from .views import *
urlpatterns = [
    path('cart/add/', AddToCartView.as_view(), name='cart-add'),
    path('cart/items/', ListCartItemsView.as_view(), name='cart-items'),
    path('create/', BuyNowView.as_view(), name='order-create'),
    path('cart/checkout/', CheckoutCartView.as_view(), name='cart-checkout'),
    path('orders/', ListOrdersView.as_view(), name='user-orders'),
    path('orders/<uuid:pk>/delivery-method/', OrderDeliveryMethodUpdateView.as_view(), name='order-delivery-method-update'),
]
