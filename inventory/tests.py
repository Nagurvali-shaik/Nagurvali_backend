from django.test import TestCase

from account.models import User
from catalog.models import Category, Product, ProductVariant
from inventory.models import Inventory, Location, StockMovement
from inventory.services import InventoryService, StockManager
from shop.models import Shop


class InventoryServiceTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            email="owner@example.com",
            password="Pass123!",
            role="SHOP_OWNER",
            marketer_type="CREATOR",
        )
        shop = Shop.objects.create(name="Test Shop", owner=user)
        category = Category.objects.create(name="Electronics", slug="electronics")
        product = Product.objects.create(
            name="Phone",
            description="Demo product",
            shop=shop,
            sku="PHONE-001",
            price="100.00",
            category=category,
        )
        variant = ProductVariant.objects.create(
            product=product,
            variant_name="Default",
            price="100.00",
        )
        location = Location.objects.create(name="Main WH", type="WAREHOUSE")
        self.inventory = Inventory.objects.create(
            variant=variant,
            location=location,
            quantity_available=20,
            quantity_reserved=0,
        )

    def test_reserve_stock_updates_inventory_and_creates_movement(self):
        success = InventoryService.reserve_stock(self.inventory, 5)

        self.assertTrue(success)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity_available, 15)
        self.assertEqual(self.inventory.quantity_reserved, 5)
        movement = StockMovement.objects.latest("id")
        self.assertEqual(movement.inventory_id, self.inventory.id)
        self.assertEqual(movement.quantity, -5)
        self.assertEqual(movement.reason, "Order Reserved")

    def test_reserve_stock_returns_false_when_not_enough_stock(self):
        success = InventoryService.reserve_stock(self.inventory, 25)

        self.assertFalse(success)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity_available, 20)
        self.assertEqual(self.inventory.quantity_reserved, 0)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_release_stock_moves_reserved_to_available(self):
        InventoryService.reserve_stock(self.inventory, 6)

        InventoryService.release_stock(self.inventory, 2)

        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity_available, 16)
        self.assertEqual(self.inventory.quantity_reserved, 4)
        movement = StockMovement.objects.latest("id")
        self.assertEqual(movement.quantity, 2)
        self.assertEqual(movement.reason, "Order Released")

    def test_confirm_stock_decreases_reserved_only(self):
        InventoryService.reserve_stock(self.inventory, 7)

        InventoryService.confirm_stock(self.inventory, 3)

        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity_available, 13)
        self.assertEqual(self.inventory.quantity_reserved, 4)
        movement = StockMovement.objects.latest("id")
        self.assertEqual(movement.quantity, -3)
        self.assertEqual(movement.reason, "Order Confirmed")

    def test_adjust_stock_changes_available_quantity(self):
        InventoryService.adjust_stock(self.inventory, -4, reason="Shrinkage")

        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity_available, 16)
        self.assertEqual(self.inventory.quantity_reserved, 0)
        movement = StockMovement.objects.latest("id")
        self.assertEqual(movement.quantity, -4)
        self.assertEqual(movement.reason, "Shrinkage")


class StockManagerTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            email="owner2@example.com",
            password="Pass123!",
            role="SHOP_OWNER",
            marketer_type="CREATOR",
        )
        shop = Shop.objects.create(name="Stock Shop", owner=user)
        category = Category.objects.create(name="Apparel", slug="apparel")
        product = Product.objects.create(
            name="T-Shirt",
            description="Demo product",
            shop=shop,
            sku="TSHIRT-001",
            price="20.00",
            category=category,
        )
        self.variant = ProductVariant.objects.create(
            product=product,
            variant_name="Blue / M",
            price="20.00",
        )
        self.inv_small = Inventory.objects.create(
            variant=self.variant,
            location=Location.objects.create(name="WH-A", type="WAREHOUSE"),
            quantity_available=2,
            quantity_reserved=0,
        )
        self.inv_large = Inventory.objects.create(
            variant=self.variant,
            location=Location.objects.create(name="WH-B", type="WAREHOUSE"),
            quantity_available=10,
            quantity_reserved=0,
        )

    def test_allocate_order_reserves_from_multiple_inventories(self):
        StockManager.allocate_order(self.variant, 5)

        self.inv_small.refresh_from_db()
        self.inv_large.refresh_from_db()
        self.assertEqual(self.inv_small.quantity_available, 0)
        self.assertEqual(self.inv_small.quantity_reserved, 2)
        self.assertEqual(self.inv_large.quantity_available, 7)
        self.assertEqual(self.inv_large.quantity_reserved, 3)
        self.assertEqual(
            StockMovement.objects.filter(reason="Order Allocation").count(), 2
        )

    def test_allocate_order_raises_when_stock_is_insufficient(self):
        with self.assertRaisesMessage(Exception, "Not enough stock to fulfill order"):
            StockManager.allocate_order(self.variant, 20)

    def test_release_order_releases_reserved_stock(self):
        StockManager.allocate_order(self.variant, 6)

        StockManager.release_order(self.variant, 4)

        self.inv_small.refresh_from_db()
        self.inv_large.refresh_from_db()
        total_reserved = self.inv_small.quantity_reserved + self.inv_large.quantity_reserved
        total_available = (
            self.inv_small.quantity_available + self.inv_large.quantity_available
        )
        self.assertEqual(total_reserved, 2)
        self.assertEqual(total_available, 10)
        self.assertEqual(StockMovement.objects.filter(reason="Order Release").count(), 2)
