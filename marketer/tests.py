from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from account.models import User
from catalog.models import Category, Product, ProductVariant
from order.models import Order, OrderItem
from shop.models import Shop

from marketer.models import MarketerContract, MarketerCommission
from marketer.services import MarketerCommissionService


class MarketerFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            email="owner@shop.com",
            password="Pass123!",
            role="SHOP_OWNER",
            marketer_type="CREATOR",
        )
        self.marketer = User.objects.create_user(
            email="marketer@shop.com",
            password="Pass123!",
            role="MARKETER",
            marketer_type="CREATOR",
        )
        self.customer = User.objects.create_user(
            email="customer@shop.com",
            password="Pass123!",
            role="CUSTOMER",
            marketer_type="CREATOR",
        )
        self.shop = Shop.objects.create(name="Test Shop", owner=self.owner)
        self.category = Category.objects.create(name="Test Cat")
        self.product = Product.objects.create(
            name="Test Product",
            shop=self.shop,
            category=self.category,
            price=Decimal("100.00"),
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            variant_name="Default",
            price=Decimal("100.00"),
            stock=10,
        )

    def _create_contract(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.post(
            "/marketer/contracts/",
            {
                "shop_id": str(self.shop.id),
                "marketer_id": str(self.marketer.id),
                "commission_rate": "10.00",
                "product_ids": [str(self.product.id)],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        return MarketerContract.objects.get(id=resp.data["id"])

    def test_contract_create_and_activate(self):
        contract = self._create_contract()
        self.assertEqual(contract.status, MarketerContract.Status.PENDING)

        activate = self.client.post(f"/marketer/contracts/{contract.id}/activate/")
        self.assertEqual(activate.status_code, 200, activate.data)
        contract.refresh_from_db()
        self.assertEqual(contract.status, MarketerContract.Status.ACTIVE)

    def test_marketer_cannot_update_contract(self):
        contract = self._create_contract()
        self.client.force_authenticate(self.marketer)
        resp = self.client.patch(
            f"/marketer/contracts/{contract.id}/",
            {"commission_rate": "12.50"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_commission_pending_then_approved(self):
        contract = self._create_contract()
        contract.status = MarketerContract.Status.ACTIVE
        contract.save(update_fields=["status", "updated_at"])

        order = Order.objects.create(
            order_number="ORD-MKT-001",
            user=self.customer,
            shop=self.shop,
            status=Order.Status.PAID,
            subtotal=Decimal("200.00"),
            total_amount=Decimal("200.00"),
            payment_method="santimpay",
            delivery_address="addr",
        )
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            variant=self.variant,
            marketer_contract=contract,
            product_name=self.product.name,
            sku=self.product.sku,
            price=Decimal("100.00"),
            quantity=2,
            total=Decimal("200.00"),
        )

        MarketerCommissionService.create_pending_for_order(order)
        commission = MarketerCommission.objects.get(order_item=item)
        self.assertEqual(commission.status, MarketerCommission.Status.PENDING)
        self.assertEqual(commission.amount, Decimal("20.00"))

        order.status = Order.Status.DELIVERED
        order.save(update_fields=["status"])

        commission.refresh_from_db()
        self.assertEqual(commission.status, MarketerCommission.Status.APPROVED)
        self.assertIsNotNone(commission.approved_at)
