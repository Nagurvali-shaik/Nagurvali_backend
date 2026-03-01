from decimal import Decimal

from django.db.models import Sum, Count
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied

from account.models import User
from order.models import OrderItem, Order
from shop.models import Shop

from .models import MarketerContract, MarketerCommission, MarketerContractProduct
from .serializers import (
    MarketerContractSerializer,
    MarketerContractUpdateSerializer,
    MarketerCommissionSerializer,
    MarketerDashboardSerializer,
)


class IsMarketerOrShopOwner(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in {"MARKETER", "SHOP_OWNER"}
        )


class MarketerDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsMarketerOrShopOwner]

    def get(self, request):
        user = request.user
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        if user.role == "MARKETER":
            commissions = MarketerCommission.objects.filter(contract__marketer=user)
            active_contracts = MarketerContract.objects.filter(
                marketer=user, status=MarketerContract.Status.ACTIVE
            ).count()
            order_items = OrderItem.objects.filter(marketer_contract__marketer=user)
        else:
            shop = getattr(user, "owned_shop", None)
            if not shop:
                payload = {
                    "total_earnings": Decimal("0.00"),
                    "pending_commissions": Decimal("0.00"),
                    "this_month_revenue": Decimal("0.00"),
                    "total_orders_influenced": 0,
                    "total_units_sold": 0,
                    "active_contracts": 0,
                    "cards": [],
                }
                return Response(MarketerDashboardSerializer(payload).data)

            commissions = MarketerCommission.objects.filter(contract__shop=shop)
            active_contracts = MarketerContract.objects.filter(
                shop=shop, status=MarketerContract.Status.ACTIVE
            ).count()
            order_items = OrderItem.objects.filter(marketer_contract__shop=shop)

        total_earnings = commissions.filter(status=MarketerCommission.Status.APPROVED).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")
        pending_commissions = commissions.filter(status=MarketerCommission.Status.PENDING).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")
        this_month_revenue = commissions.filter(
            status=MarketerCommission.Status.APPROVED,
            created_at__gte=month_start,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        total_orders_influenced = (
            order_items.values("order_id").distinct().count()
        )
        total_units_sold = order_items.aggregate(total=Sum("quantity"))["total"] or 0

        payload = {
            "total_earnings": total_earnings,
            "pending_commissions": pending_commissions,
            "this_month_revenue": this_month_revenue,
            "total_orders_influenced": total_orders_influenced,
            "total_units_sold": total_units_sold,
            "active_contracts": active_contracts,
            "cards": [
                {"title": "Total Earnings", "value": str(total_earnings)},
                {"title": "Pending Commissions", "value": str(pending_commissions)},
                {"title": "This Month Revenue", "value": str(this_month_revenue)},
                {"title": "Orders Influenced", "value": total_orders_influenced},
                {"title": "Units Sold", "value": total_units_sold},
            ],
        }
        return Response(MarketerDashboardSerializer(payload).data)


class MarketerContractListCreateView(ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsMarketerOrShopOwner]
    serializer_class = MarketerContractSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == "MARKETER":
            return MarketerContract.objects.filter(marketer=user).select_related("shop", "marketer")
        shop = getattr(user, "owned_shop", None)
        if not shop:
            return MarketerContract.objects.none()
        return MarketerContract.objects.filter(shop=shop).select_related("shop", "marketer")

    def perform_create(self, serializer):
        user = self.request.user
        shop = serializer.validated_data.get("shop")
        marketer = serializer.validated_data.get("marketer")

        if user.role == "SHOP_OWNER":
            owned_shop = getattr(user, "owned_shop", None)
            if not owned_shop or owned_shop.id != shop.id:
                raise PermissionDenied("Shop owner can only create contracts for their shop")
        elif user.role == "MARKETER":
            if marketer != user:
                raise PermissionDenied("Marketer can only create contracts for themselves")
        serializer.save()


class MarketerContractDetailView(RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsMarketerOrShopOwner]
    serializer_class = MarketerContractUpdateSerializer
    queryset = MarketerContract.objects.all()

    def get_queryset(self):
        user = self.request.user
        if user.role == "MARKETER":
            return MarketerContract.objects.filter(marketer=user)
        shop = getattr(user, "owned_shop", None)
        if not shop:
            return MarketerContract.objects.none()
        return MarketerContract.objects.filter(shop=shop)

    def update(self, request, *args, **kwargs):
        if request.user.role != "SHOP_OWNER":
            return Response({"detail": "Only shop owners can update contracts"}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)


class _ContractStatusActionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    target_status = None

    def post(self, request, pk):
        contract = MarketerContract.objects.filter(pk=pk).select_related("shop").first()
        if not contract:
            return Response({"detail": "Contract not found"}, status=status.HTTP_404_NOT_FOUND)
        user = request.user
        shop = getattr(user, "owned_shop", None)
        if not shop or contract.shop_id != shop.id:
            return Response({"detail": "Only shop owners can change contract status"}, status=status.HTTP_403_FORBIDDEN)
        contract.status = self.target_status
        contract.save(update_fields=["status", "updated_at"])
        return Response({"id": str(contract.id), "status": contract.status})


class MarketerContractActivateView(_ContractStatusActionView):
    target_status = MarketerContract.Status.ACTIVE


class MarketerContractPauseView(_ContractStatusActionView):
    target_status = MarketerContract.Status.PAUSED


class MarketerContractResumeView(_ContractStatusActionView):
    target_status = MarketerContract.Status.ACTIVE


class MarketerContractEndView(_ContractStatusActionView):
    target_status = MarketerContract.Status.ENDED


class MarketerCommissionListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsMarketerOrShopOwner]

    def get(self, request):
        user = request.user
        if user.role == "MARKETER":
            qs = MarketerCommission.objects.filter(contract__marketer=user)
        else:
            shop = getattr(user, "owned_shop", None)
            if not shop:
                return Response([])
            qs = MarketerCommission.objects.filter(contract__shop=shop)
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        serializer = MarketerCommissionSerializer(qs.order_by("-created_at"), many=True)
        return Response(serializer.data)

# Create your views here.
