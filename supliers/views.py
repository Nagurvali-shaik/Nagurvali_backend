from decimal import Decimal

from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Product, ProductMedia, ProductVariant
from order.models import Order, OrderItem
from payment.models import Earning, Payment

from .serializers import (
    SupplierDashboardSerializer,
    SupplierProductMediaSerializer,
    SupplierProductSerializer,
    SupplierProductVariantSerializer,
    SupplierStockUpdateSerializer,
)


class IsSupplier(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "SUPPLIER")


def _supplier_order_items(user):
    return OrderItem.objects.select_related("order", "product", "variant__product").filter(
        Q(product__supplier=user) | Q(variant__product__supplier=user)
    )


class SupplierDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSupplier]

    def get(self, request):
        supplier = request.user
        sale_statuses = {
            Order.Status.PAID,
            Order.Status.CONFIRMED,
            Order.Status.PROCESSING,
            Order.Status.SHIPPED,
            Order.Status.DELIVERED,
        }
        orders_supplied_statuses = sale_statuses | {Order.Status.REFUNDED}

        items = list(_supplier_order_items(supplier))
        if not items:
            payload = {
                "total_earnings": Decimal("0.00"),
                "total_units_sold": 0,
                "orders_supplied": 0,
                "pending_payout": Decimal("0.00"),
                "this_month_revenue": Decimal("0.00"),
                "cards": [
                    {"title": "💰 Total Earnings", "value": "0.00"},
                    {"title": "📦 Total Units Sold", "value": 0},
                    {"title": "🛒 Orders Supplied", "value": 0},
                    {"title": "⏳ Pending Payout", "value": "0.00"},
                    {"title": "📊 This Month Revenue", "value": "0.00"},
                ],
            }
            return Response(SupplierDashboardSerializer(payload).data)

        order_ids = {item.order_id for item in items}
        payment_map = {}
        for payment in Payment.objects.filter(order_id__in=order_ids).order_by("-created_at"):
            payment_map.setdefault(payment.order_id, payment)

        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        total_earnings = Decimal("0.00")
        total_units_sold = 0
        pending_payout = Decimal("0.00")
        this_month_revenue = Decimal("0.00")
        supplied_orders = set()

        for item in items:
            product = item.product if item.product else (item.variant.product if item.variant else None)
            if not product:
                continue
            order = item.order
            line_amount = (product.supplier_price if product.supplier_price is not None else item.price) * item.quantity

            if order.status in orders_supplied_statuses:
                supplied_orders.add(order.id)

            if order.status in sale_statuses:
                total_earnings += Decimal(str(line_amount))
                total_units_sold += int(item.quantity)
                if order.created_at >= month_start:
                    this_month_revenue += Decimal(str(line_amount))

                payment = payment_map.get(order.id)
                if payment and payment.status == Payment.Status.COMPLETED:
                    pass

        earning_rows = Earning.objects.filter(user=supplier)
        total_earnings = sum((row.amount for row in earning_rows), Decimal("0.00"))
        pending_payout = sum(
            (row.amount for row in earning_rows.filter(status=Earning.Status.AVAILABLE)),
            Decimal("0.00"),
        )

        payload = {
            "total_earnings": total_earnings.quantize(Decimal("0.01")),
            "total_units_sold": total_units_sold,
            "orders_supplied": len(supplied_orders),
            "pending_payout": pending_payout.quantize(Decimal("0.01")),
            "this_month_revenue": this_month_revenue.quantize(Decimal("0.01")),
            "cards": [
                {"title": "💰 Total Earnings", "value": str(total_earnings.quantize(Decimal("0.01")))},
                {"title": "📦 Total Units Sold", "value": total_units_sold},
                {"title": "🛒 Orders Supplied", "value": len(supplied_orders)},
                {"title": "⏳ Pending Payout", "value": str(pending_payout.quantize(Decimal("0.01")))},
                {"title": "📊 This Month Revenue", "value": str(this_month_revenue.quantize(Decimal("0.01")))},
            ],
        }
        return Response(SupplierDashboardSerializer(payload).data)


class SupplierProductListCreateView(ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsSupplier]
    serializer_class = SupplierProductSerializer

    def get_queryset(self):
        return Product.objects.filter(supplier=self.request.user).select_related("category").prefetch_related("variants", "media")


class SupplierProductDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsSupplier]
    serializer_class = SupplierProductSerializer

    def get_queryset(self):
        return Product.objects.filter(supplier=self.request.user).select_related("category").prefetch_related("variants", "media")


class SupplierProductVariantCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSupplier]

    def post(self, request, pk):
        product = Product.objects.filter(pk=pk, supplier=request.user).first()
        if not product:
            return Response({"detail": "Supplier product not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = SupplierProductVariantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        variant = serializer.save(product=product)
        return Response(SupplierProductVariantSerializer(variant).data, status=status.HTTP_201_CREATED)


class SupplierProductMediaCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSupplier]

    def post(self, request, pk):
        product = Product.objects.filter(pk=pk, supplier=request.user).first()
        if not product:
            return Response({"detail": "Supplier product not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = SupplierProductMediaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        media = serializer.save(product=product)
        return Response(SupplierProductMediaSerializer(media).data, status=status.HTTP_201_CREATED)


class SupplierVariantStockUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSupplier]

    def patch(self, request, pk):
        variant = ProductVariant.objects.filter(pk=pk, product__supplier=request.user).select_related("product").first()
        if not variant:
            return Response({"detail": "Variant not found for this supplier."}, status=status.HTTP_404_NOT_FOUND)
        serializer = SupplierStockUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        variant.stock = serializer.validated_data["stock"]
        variant.save(update_fields=["stock", "updated_at"])
        return Response(
            {
                "variant_id": str(variant.id),
                "product_id": str(variant.product_id),
                "stock": variant.stock,
                "message": "Stock updated successfully.",
            }
        )


class SupplierLowStockAlertView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSupplier]

    def get(self, request):
        threshold = request.query_params.get("threshold", 5)
        try:
            threshold = int(threshold)
        except (TypeError, ValueError):
            return Response({"detail": "threshold must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
        if threshold < 0:
            return Response({"detail": "threshold must be >= 0."}, status=status.HTTP_400_BAD_REQUEST)

        variants = (
            ProductVariant.objects.filter(product__supplier=request.user, stock__lte=threshold)
            .select_related("product")
            .order_by("stock", "product__name")
        )
        alerts = [
            {
                "variant_id": str(variant.id),
                "product_id": str(variant.product_id),
                "product_name": variant.product.name,
                "variant_name": variant.variant_name,
                "stock": variant.stock,
                "threshold": threshold,
                "is_low_stock": True,
            }
            for variant in variants
        ]
        return Response({"count": len(alerts), "alerts": alerts})
