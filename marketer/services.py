from decimal import Decimal

from django.utils import timezone

from catalog.models import Product
from order.models import Order, OrderItem
from .models import MarketerContract, MarketerContractProduct, MarketerCommission


class MarketerContractService:
    @staticmethod
    def is_product_allowed(contract: MarketerContract, product: Product) -> bool:
        return MarketerContractProduct.objects.filter(contract=contract, product=product).exists()

    @staticmethod
    def validate_contract_for_product(contract: MarketerContract, product: Product) -> None:
        if not contract.is_active():
            raise ValueError("Contract is not active")
        if product.shop_id != contract.shop_id:
            raise ValueError("Product does not belong to the contract shop")
        if not MarketerContractService.is_product_allowed(contract, product):
            raise ValueError("Product is not part of the contract")


class MarketerCommissionService:
    @staticmethod
    def _calculate_amount(rate_percent: Decimal, base_amount: Decimal) -> Decimal:
        return (base_amount * rate_percent / Decimal("100.00")).quantize(Decimal("0.01"))

    @staticmethod
    def create_pending_for_order(order: Order):
        items = (
            order.items.select_related("product", "variant__product", "marketer_contract")
            .all()
        )
        created_commissions = []
        for item in items:
            contract = getattr(item, "marketer_contract", None)
            if not contract or not contract.is_active():
                continue
            product = item.product if item.product else (item.variant.product if item.variant else None)
            if not product:
                continue
            if product.shop_id != contract.shop_id:
                continue
            if not MarketerContractProduct.objects.filter(contract=contract, product=product).exists():
                continue

            base_amount = Decimal(str(item.total))
            rate = Decimal(str(contract.commission_rate))
            amount = MarketerCommissionService._calculate_amount(rate, base_amount)
            if amount <= Decimal("0.00"):
                continue

            commission, created = MarketerCommission.objects.get_or_create(
                contract=contract,
                order=order,
                order_item=item,
                product=product,
                defaults={
                    "rate": rate,
                    "amount": amount,
                    "status": MarketerCommission.Status.PENDING,
                },
            )
            if created:
                created_commissions.append(commission)
        return created_commissions

    @staticmethod
    def approve_for_order(order: Order):
        now = timezone.now()
        commissions = list(
            MarketerCommission.objects.filter(
                order=order,
                status=MarketerCommission.Status.PENDING,
            )
        )
        if not commissions:
            return []
        MarketerCommission.objects.filter(
            order=order,
            status=MarketerCommission.Status.PENDING,
        ).update(status=MarketerCommission.Status.APPROVED, approved_at=now)
        for commission in commissions:
            commission.status = MarketerCommission.Status.APPROVED
            commission.approved_at = now
        return commissions
