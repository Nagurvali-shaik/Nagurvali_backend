from rest_framework import status
from rest_framework.test import APITestCase
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import threading

from django.db import close_old_connections
from django.test import TransactionTestCase
from account.models import User
from catalog.models import Category, Product, ProductVariant
from shop.models import Shop

from .models import Cart, CartItem, Order
from .services import OrderService


class OrderViewsTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner_order_tests@example.com",
            password="pass1234",
            role="SHOP_OWNER",
            marketer_type="CREATOR",
        )
        self.buyer = User.objects.create_user(
            email="buyer_order_tests@example.com",
            password="pass1234",
            role="CUSTOMER",
            marketer_type="CREATOR",
        )

        self.shop = Shop.objects.create(name="Order Test Shop", owner=self.owner)
        self.category = Category.objects.create(name="Order Test Category")
        self.product = Product.objects.create(
            name="Order Test Product",
            shop=self.shop,
            category=self.category,
            price="100.00",
            description="test",
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            variant_name="Default",
            price="120.00",
            stock=20,
        )

        self.client.force_authenticate(user=self.buyer)

    def test_buynow_creates_order_and_generates_unique_order_numbers(self):
        payload = {
            "shop_id": str(self.shop.id),
            "product_id": str(self.product.id),
            "variant_id": str(self.variant.id),
            "quantity": 1,
            "delivery_address": "123 Main St",
            "payment_method": "santimpay",
        }

        first = self.client.post("/order/create/", payload, format="json")
        second = self.client.post("/order/create/", payload, format="json")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Order.objects.count(), 2)

        numbers = list(Order.objects.values_list("order_number", flat=True))
        self.assertEqual(len(numbers), len(set(numbers)))
        for order_number in numbers:
            self.assertTrue(order_number)

    def test_buynow_supports_seller_delivery_method(self):
        payload = {
            "shop_id": str(self.shop.id),
            "product_id": str(self.product.id),
            "variant_id": str(self.variant.id),
            "quantity": 1,
            "delivery_address": "123 Main St",
            "payment_method": "santimpay",
            "delivery_method": "seller",
        }
        response = self.client.post("/order/create/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        order = Order.objects.get(id=response.data["order_id"])
        self.assertEqual(order.delivery_method, Order.DeliveryMethod.SELLER)

    def test_checkout_cart_creates_order_from_active_cart(self):
        cart = Cart.objects.create(user=self.buyer, shop=self.shop, is_active=True)
        CartItem.objects.create(cart=cart, product=self.product, variant=self.variant, quantity=2)

        response = self.client.post(
            "/order/cart/checkout/",
            {
                "delivery_address": "123 Main St",
                "payment_method": "santimpay",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.shop_id, self.shop.id)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().quantity, 2)
        cart.refresh_from_db()
        self.assertFalse(cart.is_active)
        self.assertEqual(cart.items.count(), 0)

    def test_checkout_cart_cannot_be_reused_after_success(self):
        cart = Cart.objects.create(user=self.buyer, shop=self.shop, is_active=True)
        CartItem.objects.create(cart=cart, product=self.product, variant=self.variant, quantity=1)

        first = self.client.post(
            "/order/cart/checkout/",
            {"delivery_address": "123 Main St", "payment_method": "santimpay"},
            format="json",
        )
        second = self.client.post(
            "/order/cart/checkout/",
            {"delivery_address": "123 Main St", "payment_method": "santimpay"},
            format="json",
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST, second.data)
        self.assertEqual(Order.objects.count(), 1)

    def test_shop_owner_can_change_delivery_method_before_shipment(self):
        create_resp = self.client.post(
            "/order/create/",
            {
                "shop_id": str(self.shop.id),
                "product_id": str(self.product.id),
                "variant_id": str(self.variant.id),
                "quantity": 1,
                "delivery_address": "123 Main St",
                "payment_method": "santimpay",
            },
            format="json",
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED, create_resp.data)
        order_id = create_resp.data["order_id"]

        owner_client = self.client_class()
        owner_client.force_authenticate(user=self.owner)
        patch_resp = owner_client.patch(
            f"/order/orders/{order_id}/delivery-method/",
            {"delivery_method": "seller"},
            format="json",
        )
        self.assertEqual(patch_resp.status_code, status.HTTP_200_OK, patch_resp.data)
        self.assertEqual(patch_resp.data["delivery_method"], "seller")

    def test_list_orders_returns_user_orders(self):
        payload = {
            "shop_id": str(self.shop.id),
            "product_id": str(self.product.id),
            "variant_id": str(self.variant.id),
            "quantity": 1,
            "delivery_address": "123 Main St",
            "payment_method": "santimpay",
        }
        self.client.post("/order/create/", payload, format="json")

        response = self.client.get("/order/orders/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("orders", response.data)
        self.assertEqual(len(response.data["orders"]), 1)

    def test_buynow_without_variant_id_uses_default_variant(self):
        product_without_variant = Product.objects.create(
            name="Order Test Product No Variant",
            shop=self.shop,
            category=self.category,
            price="60.00",
            description="test no variant",
        )
        ProductVariant.objects.create(
            product=product_without_variant,
            variant_name="Default",
            price="60.00",
            stock=15,
        )

        payload = {
            "shop_id": str(self.shop.id),
            "product_id": str(product_without_variant.id),
            "quantity": 1,
            "delivery_address": "123 Main St",
            "payment_method": "santimpay",
        }

        response = self.client.post("/order/create/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        created = Order.objects.get(id=response.data["order_id"])
        self.assertEqual(created.items.count(), 1)
        self.assertIsNotNone(created.items.first().variant_id)

    def test_buynow_without_variant_picks_first_in_stock_variant(self):
        product = Product.objects.create(
            name="Stock Selection Product",
            shop=self.shop,
            category=self.category,
            price=Decimal("80.00"),
            description="variant selection",
        )
        out_of_stock = ProductVariant.objects.create(
            product=product,
            variant_name="Out",
            price=Decimal("75.00"),
            stock=0,
        )
        in_stock = ProductVariant.objects.create(
            product=product,
            variant_name="In",
            price=Decimal("90.00"),
            stock=5,
        )

        payload = {
            "shop_id": str(self.shop.id),
            "product_id": str(product.id),
            "quantity": 2,
            "delivery_address": "123 Main St",
            "payment_method": "santimpay",
        }
        response = self.client.post("/order/create/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        order = Order.objects.get(id=response.data["order_id"])
        item = order.items.first()
        self.assertEqual(item.variant_id, in_stock.id)
        self.assertNotEqual(item.variant_id, out_of_stock.id)

    def test_add_to_cart_without_variant_picks_first_in_stock_variant(self):
        product = Product.objects.create(
            name="Cart Stock Selection Product",
            shop=self.shop,
            category=self.category,
            price=Decimal("50.00"),
            description="cart variant selection",
        )
        ProductVariant.objects.create(
            product=product,
            variant_name="Out",
            price=Decimal("45.00"),
            stock=0,
        )
        in_stock = ProductVariant.objects.create(
            product=product,
            variant_name="In",
            price=Decimal("55.00"),
            stock=2,
        )

        response = self.client.post(
            "/order/cart/add/",
            {"shop_id": str(self.shop.id), "product_id": str(product.id), "quantity": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        cart = Cart.objects.get(user=self.buyer, shop=self.shop, is_active=True)
        self.assertEqual(cart.items.count(), 1)
        self.assertEqual(cart.items.first().variant_id, in_stock.id)

    def test_buynow_uses_product_price_when_variant_price_is_null(self):
        product = Product.objects.create(
            name="Null Variant Price Product",
            shop=self.shop,
            category=self.category,
            price=Decimal("99.00"),
            description="null variant price",
        )
        variant = ProductVariant.objects.create(
            product=product,
            variant_name="No Variant Price",
            price=None,
            stock=3,
        )

        response = self.client.post(
            "/order/create/",
            {
                "shop_id": str(self.shop.id),
                "product_id": str(product.id),
                "variant_id": str(variant.id),
                "quantity": 2,
                "delivery_address": "123 Main St",
                "payment_method": "santimpay",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        order = Order.objects.get(id=response.data["order_id"])
        item = order.items.first()
        self.assertEqual(item.price, Decimal("99.00"))
        self.assertEqual(item.total, Decimal("198.00"))
        self.assertEqual(order.subtotal, Decimal("198.00"))

    def test_add_to_cart_response_uses_product_price_when_variant_price_is_null(self):
        product = Product.objects.create(
            name="Cart Null Variant Price Product",
            shop=self.shop,
            category=self.category,
            price=Decimal("33.00"),
            description="null variant price for cart",
        )
        variant = ProductVariant.objects.create(
            product=product,
            variant_name="No Price",
            price=None,
            stock=4,
        )

        response = self.client.post(
            "/order/cart/add/",
            {
                "shop_id": str(self.shop.id),
                "product_id": str(product.id),
                "variant_id": str(variant.id),
                "quantity": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(Decimal(str(response.data["subtotal"])), Decimal("66.00"))
        self.assertEqual(Decimal(str(response.data["items"][0]["price"])), Decimal("33.00"))

    def test_list_orders_uses_product_price_when_variant_price_is_null(self):
        product = Product.objects.create(
            name="List Null Variant Price Product",
            shop=self.shop,
            category=self.category,
            price=Decimal("44.00"),
            description="list order null price",
        )
        variant = ProductVariant.objects.create(
            product=product,
            variant_name="No Price",
            price=None,
            stock=2,
        )
        self.client.post(
            "/order/create/",
            {
                "shop_id": str(self.shop.id),
                "product_id": str(product.id),
                "variant_id": str(variant.id),
                "quantity": 1,
                "delivery_address": "123 Main St",
                "payment_method": "santimpay",
            },
            format="json",
        )

        response = self.client.get("/order/orders/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(str(response.data["orders"][0]["items"][0]["price"])), Decimal("44.00"))

    def test_create_order_decrements_stock(self):
        start_stock = self.variant.stock
        response = self.client.post(
            "/order/create/",
            {
                "shop_id": str(self.shop.id),
                "product_id": str(self.product.id),
                "variant_id": str(self.variant.id),
                "quantity": 3,
                "delivery_address": "123 Main St",
                "payment_method": "santimpay",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, start_stock - 3)

    def test_create_order_rejects_when_combined_quantity_for_same_variant_exceeds_stock(self):
        with self.assertRaisesMessage(ValueError, "Insufficient stock"):
            OrderService.create_order(
                user=self.buyer,
                shop=self.shop,
                items=[
                    {"product": self.product, "variant": self.variant, "quantity": 15},
                    {"product": self.product, "variant": self.variant, "quantity": 10},
                ],
                delivery_address="123 Main St",
                payment_method="santimpay",
            )

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 20)


class OrderConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner_order_conc@example.com",
            password="pass1234",
            role="SHOP_OWNER",
            marketer_type="CREATOR",
        )
        self.buyer = User.objects.create_user(
            email="buyer_order_conc@example.com",
            password="pass1234",
            role="CUSTOMER",
            marketer_type="CREATOR",
        )

        self.shop = Shop.objects.create(name="Order Concurrency Shop", owner=self.owner)
        self.category = Category.objects.create(name="Order Concurrency Category")
        self.product = Product.objects.create(
            name="Order Concurrency Product",
            shop=self.shop,
            category=self.category,
            price="100.00",
            description="test",
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            variant_name="Default",
            price="120.00",
            stock=10,
        )

    def _attempt_order_create(self, barrier):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            order = OrderService.create_order(
                user=self.buyer,
                shop=self.shop,
                items=[{"product": self.product, "variant": self.variant, "quantity": 7}],
                delivery_address="123 Main St",
                payment_method="santimpay",
            )
            return ("ok", str(order.id))
        except Exception as exc:
            return ("err", str(exc))
        finally:
            close_old_connections()

    def test_parallel_orders_only_one_succeeds_for_limited_stock(self):
        barrier = threading.Barrier(2)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self._attempt_order_create, barrier) for _ in range(2)]
            results = [f.result(timeout=20) for f in futures]

        success_count = len([r for r in results if r[0] == "ok"])
        error_count = len([r for r in results if r[0] == "err"])
        self.assertEqual(success_count, 1, results)
        self.assertEqual(error_count, 1, results)

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 3)
        self.assertEqual(Order.objects.count(), 1)
        combined_error = (results[0][1] + " " + results[1][1]).lower()
        self.assertTrue(
            ("insufficient stock" in combined_error) or ("table is locked" in combined_error),
            results,
        )
