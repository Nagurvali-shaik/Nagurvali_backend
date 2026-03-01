from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from account.models import User
from catalog.models import Product, ProductVariant


class SupplierAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.supplier = User.objects.create_user(
            email="supplier@example.com",
            password="Pass123!",
            role="SUPPLIER",
            marketer_type="CREATOR",
        )
        self.customer = User.objects.create_user(
            email="customer@example.com",
            password="Pass123!",
            role="CUSTOMER",
            marketer_type="CREATOR",
        )

    def test_supplier_can_create_product_with_supplier_fields(self):
        self.client.force_authenticate(user=self.supplier)
        payload = {
            "name": "Supplier Coffee Beans",
            "description": "Premium beans",
            "price": "250.00",
            "supplier_price": "180.00",
            "minimum_wholesale_quantity": 12,
        }

        response = self.client.post("/supliers/products/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)

        product = Product.objects.get(id=response.data["id"])
        self.assertEqual(product.supplier_id, self.supplier.id)
        self.assertIsNone(product.shop)
        self.assertEqual(product.minimum_wholesale_quantity, 12)
        self.assertEqual(product.supplier_price, Decimal("180.00"))

    def test_non_supplier_cannot_access_supplier_products(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.get("/supliers/products/")
        self.assertEqual(response.status_code, 403)

    def test_supplier_can_create_variant_and_update_stock(self):
        product = Product.objects.create(
            name="Supplier Product A",
            supplier=self.supplier,
            price=Decimal("100.00"),
            supplier_price=Decimal("70.00"),
            minimum_wholesale_quantity=5,
        )
        self.client.force_authenticate(user=self.supplier)

        create_variant = self.client.post(
            f"/supliers/products/{product.id}/variants/",
            {
                "variant_name": "Red XL",
                "price": "120.00",
                "attributes": {"color": "red", "size": "xl"},
                "stock": 3,
            },
            format="json",
        )
        self.assertEqual(create_variant.status_code, 201, create_variant.data)
        variant_id = create_variant.data["id"]

        update_stock = self.client.patch(
            f"/supliers/variants/{variant_id}/stock/",
            {"stock": 25},
            format="json",
        )
        self.assertEqual(update_stock.status_code, 200, update_stock.data)

        variant = ProductVariant.objects.get(id=variant_id)
        self.assertEqual(variant.stock, 25)

    def test_low_stock_alerts_return_supplier_variants(self):
        product = Product.objects.create(
            name="Supplier Product B",
            supplier=self.supplier,
            price=Decimal("90.00"),
            supplier_price=Decimal("60.00"),
            minimum_wholesale_quantity=3,
        )
        ProductVariant.objects.create(product=product, variant_name="S", stock=2, price=Decimal("90.00"))
        ProductVariant.objects.create(product=product, variant_name="M", stock=10, price=Decimal("90.00"))

        self.client.force_authenticate(user=self.supplier)
        response = self.client.get("/supliers/alerts/low-stock/?threshold=5")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["alerts"][0]["variant_name"], "S")

    def test_supplier_dashboard_returns_expected_keys(self):
        self.client.force_authenticate(user=self.supplier)
        response = self.client.get("/supliers/dashboard/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("total_earnings", response.data)
        self.assertIn("total_units_sold", response.data)
        self.assertIn("orders_supplied", response.data)
        self.assertIn("pending_payout", response.data)
        self.assertIn("this_month_revenue", response.data)
        self.assertEqual(len(response.data["cards"]), 5)
