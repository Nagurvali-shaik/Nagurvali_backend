from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.db import transaction
from .serializers import CartItemCreateSerializer
from .services import CartService, OrderService 
from .models import *
from marketer.models import MarketerContract


def _item_unit_price(product, variant=None):
    if variant and variant.price is not None:
        return variant.price
    return product.price


class AddToCartView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        serializer = CartItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            cart = CartService.add_to_cart(
                user=request.user,
                **serializer.validated_data
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Optional: return cart summary
        items = cart.items.select_related("product", "variant").all()
        subtotal = sum(
            _item_unit_price(i.product, i.variant) * i.quantity for i in items
        )
        data = [
            {
                "id": i.id,
                "product": i.product.name,
                "variant": i.variant.variant_name if i.variant else None,
                "marketer_contract_id": str(i.marketer_contract_id) if i.marketer_contract_id else None,
                "quantity": i.quantity,
                "price": _item_unit_price(i.product, i.variant)
            } for i in items
        ]

        return Response({
            "message": "Item added successfully",
            "cart_id": str(cart.id),
            "items_count": items.count(),
            "subtotal": subtotal,
            "items": data
        }, status=status.HTTP_200_OK)
class ListCartItemsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cart = Cart.objects.filter(user=request.user, is_active=True).first()
        if not cart:
            return Response({"items": []})

        items = CartItem.objects.filter(cart=cart).select_related('product', 'variant')
        data = []
        for item in items:
            data.append({
                "id": item.id,
                "product": item.product.name,
                "variant": item.variant.variant_name if item.variant else None,
                "marketer_contract_id": str(item.marketer_contract_id) if item.marketer_contract_id else None,
                "quantity": item.quantity,
                "price": _item_unit_price(item.product, item.variant)
            })

        return Response({"items": data})




class BuyNowView(APIView):
    def post(self, request):
        data = request.data

        # Manual validation
        shop_id = data.get("shop_id")
        product_id = data.get("product_id")
        variant_id = data.get("variant_id")
        marketer_contract_id = data.get("marketer_contract_id")
        quantity = data.get("quantity", 1)
        delivery_address = data.get("delivery_address")
        payment_method = data.get("payment_method")
        delivery_method = data.get("delivery_method", Order.DeliveryMethod.COURIER)

        if not shop_id or not product_id or not delivery_address or not payment_method:
            return Response({"detail": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            shop = Shop.objects.get(id=shop_id)
            product = Product.objects.get(id=product_id, shop=shop)
            variant = ProductVariant.objects.get(id=variant_id, product=product) if variant_id else None
            marketer_contract = None
            if marketer_contract_id:
                marketer_contract = MarketerContract.objects.filter(id=marketer_contract_id).first()
                if not marketer_contract:
                    return Response({"detail": "Invalid marketer_contract_id"}, status=status.HTTP_400_BAD_REQUEST)
        except (Shop.DoesNotExist, Product.DoesNotExist, ProductVariant.DoesNotExist):
            return Response({"detail": "Invalid product/shop/variant"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if delivery_method not in {Order.DeliveryMethod.COURIER, Order.DeliveryMethod.SELLER}:
                return Response({"detail": "Invalid delivery_method"}, status=status.HTTP_400_BAD_REQUEST)
            order = OrderService.create_order(
                user=request.user,
                shop=shop,
                items=[{"product": product, "variant": variant, "quantity": int(quantity), "marketer_contract": marketer_contract}],
                delivery_address=delivery_address,
                payment_method=payment_method,
                delivery_method=delivery_method,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "order_id": str(order.id),
            "status": order.status,
            "delivery_method": order.delivery_method,
        }, status=status.HTTP_201_CREATED)
    
# e.g
# {
#   "shop_id": "591fa1ee-87ae-4b1a-96eb-c2860df9d9b9",
#   "product_id": "223be6e6-5752-441f-82e6-14f2812acb84",
#   "variant_id": "90439833-ef6a-4c95-8a41-d32d9ae1d3fd",
#   "quantity": 2,
#   "delivery_address": "123 Main St, Hosa'ina, Ethiopia",
#   "payment_method": "santimpay"
# }

class CheckoutCartView(APIView):
    """
    Create an order from the user's active cart.
    """

    def post(self, request):
        user = request.user
        delivery_address = request.data.get("delivery_address")
        payment_method = request.data.get("payment_method")
        delivery_method = request.data.get("delivery_method", Order.DeliveryMethod.COURIER)

        if not delivery_address or not payment_method:
            return Response(
                {"detail": "delivery_address and payment_method are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get the active cart
        cart = Cart.objects.filter(user=user, is_active=True).first()
        if not cart or not cart.items.exists():
            return Response({"detail": "No active cart or cart is empty"}, status=status.HTTP_400_BAD_REQUEST)

        items = [
            {
                "product": item.product,
                "variant": item.variant,
                "quantity": item.quantity,
                "marketer_contract": item.marketer_contract,
            }
            for item in cart.items.select_related("product", "variant", "marketer_contract").all()
        ]

        try:
            if delivery_method not in {Order.DeliveryMethod.COURIER, Order.DeliveryMethod.SELLER}:
                return Response({"detail": "Invalid delivery_method"}, status=status.HTTP_400_BAD_REQUEST)
            with transaction.atomic():
                order = OrderService.create_order(
                    user=user,
                    shop=cart.shop,
                    items=items,
                    delivery_address=delivery_address,
                    payment_method=payment_method,
                    delivery_method=delivery_method,
                )
                cart.items.all().delete()
                cart.is_active = False
                cart.save(update_fields=["is_active", "updated_at"])
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "order_id": str(order.id),
            "status": order.status,
            "delivery_method": order.delivery_method,
            "total_amount": float(order.total_amount)
        }, status=status.HTTP_201_CREATED)
#   e.g  
# {
#   "delivery_address": "123 Main St",
#   "payment_method": "santimpay"
# }

class ListOrdersView(APIView):
    def get(self, request):
        orders = Order.objects.filter(user=request.user).order_by("-created_at")
        data = []
        for order in orders:
            data.append({
                "id": str(order.id),
                "shop": order.shop.name,
                "status": order.status,
                "delivery_method": order.delivery_method,
                "total_amount": float(order.total_amount),
                "created_at": order.created_at.isoformat(),
                "items": [
                    {
                        "product": item.product.name,
                        "variant": item.variant.variant_name if item.variant else None,
                        "quantity": item.quantity,
                        "price": float(_item_unit_price(item.product, item.variant))
                    } for item in order.items.select_related("product", "variant").all()
                ]
            })
        return Response({"orders": data})


class OrderDeliveryMethodUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        order = Order.objects.select_related("shop__owner").filter(pk=pk).first()
        if not order:
            return Response({"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
        if order.shop.owner_id != request.user.id:
            return Response({"detail": "Only shop owner can update delivery method"}, status=status.HTTP_403_FORBIDDEN)

        method = request.data.get("delivery_method")
        if method not in {Order.DeliveryMethod.COURIER, Order.DeliveryMethod.SELLER}:
            return Response({"detail": "Invalid delivery_method"}, status=status.HTTP_400_BAD_REQUEST)

        if hasattr(order, "shipment"):
            return Response({"detail": "Delivery method cannot change after shipment is created"}, status=status.HTTP_400_BAD_REQUEST)
        if order.status in {Order.Status.SHIPPED, Order.Status.DELIVERED, Order.Status.CANCELLED, Order.Status.REFUNDED}:
            return Response({"detail": "Delivery method cannot change in current order status"}, status=status.HTTP_400_BAD_REQUEST)

        order.delivery_method = method
        order.save(update_fields=["delivery_method", "updated_at"])
        return Response({"order_id": str(order.id), "delivery_method": order.delivery_method}, status=status.HTTP_200_OK)
