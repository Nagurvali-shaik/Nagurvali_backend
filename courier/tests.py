from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase
from rest_framework.test import APIClient

from account.models import User
from catalog.models import Category, Product, ProductVariant
from courier.models import CourierPartner, Shipment
from courier.services import create_shipment_for_order
from order.models import Order, OrderItem
from shop.models import Shop


class CourierFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            email="owner_courier@example.com",
            password="Pass123!",
            role="SHOP_OWNER",
            marketer_type="CREATOR",
            merchant_id="merchant-owner",
        )
        self.customer = User.objects.create_user(
            email="customer_courier@example.com",
            password="Pass123!",
            role="CUSTOMER",
            marketer_type="CREATOR",
        )
        self.shop = Shop.objects.create(name="Courier Shop", owner=self.owner)
        self.category = Category.objects.create(name="Courier Category")
        self.product = Product.objects.create(
            name="Courier Product",
            shop=self.shop,
            category=self.category,
            price=Decimal("100.00"),
            supplier_price=Decimal("70.00"),
            minimum_wholesale_quantity=1,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, variant_name="Default", price=Decimal("100.00"), stock=20
        )
        self.order = Order.objects.create(
            order_number="ORD-COURIER-001",
            user=self.customer,
            shop=self.shop,
            status=Order.Status.PAID,
            subtotal=Decimal("100.00"),
            total_amount=Decimal("100.00"),
            payment_method="santimpay",
            delivery_address="Addis Ababa",
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            variant=self.variant,
            product_name=self.product.name,
            sku=self.product.sku,
            price=Decimal("100.00"),
            quantity=1,
            total=Decimal("100.00"),
        )
        self.partner = CourierPartner.objects.create(name="Hudhud", provider_code="hudhud", is_active=True, priority=1)

    def test_create_shipment_for_paid_order(self):
        shipment = create_shipment_for_order(self.order)
        self.assertEqual(shipment.order_id, self.order.id)
        self.assertEqual(shipment.courier_id, self.partner.id)
        self.assertEqual(shipment.status, Shipment.Status.CREATED)
        self.assertTrue(shipment.external_tracking_id)

    def test_webhook_delivered_updates_order_status(self):
        shipment = create_shipment_for_order(self.order)
        response = self.client.post(
            "/logistics/webhook/hudhud/",
            {
                "tracking_id": shipment.external_tracking_id,
                "status": "DELIVERED",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        shipment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(shipment.status, Shipment.Status.DELIVERED)
        self.assertEqual(self.order.status, Order.Status.DELIVERED)

    @patch("courier.services.requests.post")
    def test_create_shipment_calls_external_courier_api_when_base_url_set(self, mock_post):
        self.partner.api_base_url = "https://api.hudhud.example"
        self.partner.api_key = "secret-token"
        self.partner.save(update_fields=["api_base_url", "api_key"])

        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "id": "SHIP-1001",
            "tracking_id": "HDX-1001",
            "status": "CREATED",
        }
        mock_post.return_value = mock_resp

        shipment = create_shipment_for_order(self.order)

        self.assertEqual(shipment.external_shipment_id, "SHIP-1001")
        self.assertEqual(shipment.external_tracking_id, "HDX-1001")
        self.assertEqual(shipment.status, Shipment.Status.CREATED)
        self.assertEqual(mock_post.call_count, 1)
        called_url = mock_post.call_args.args[0]
        self.assertEqual(called_url, "https://api.hudhud.example/shipments")
