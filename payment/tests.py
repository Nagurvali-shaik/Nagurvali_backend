from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from account.models import User
from catalog.models import Category, Product, ProductVariant
from order.models import Order, OrderItem
from payment.models import Earning, Payment
from payment.services.service import PaymentService, PaymentServiceError
from shop.models import Shop


@override_settings(
    SANTIMPAY_PRIVATE_KEY="dummy-private-key",
    SANTIMPAY_TEST_BED=True,
    SANTIMPAY_NOTIFY_URL="http://localhost:8000/payment/webhook/santimpay/",
)
class PayoutRequestTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.shop_owner = User.objects.create_user(
            email="owner@shop.com",
            password="Pass123!",
            role="SHOP_OWNER",
            merchant_id="OWNER-MERCHANT-001",
            marketer_type="CREATOR",
            phone_number="0911000000",
        )
        self.supplier = User.objects.create_user(
            email="supplier@shop.com",
            password="Pass123!",
            role="SUPPLIER",
            merchant_id="SUP-MERCHANT-001",
            marketer_type="CREATOR",
            phone_number="0911223344",
        )
        self.customer = User.objects.create_user(
            email="customer@shop.com",
            password="Pass123!",
            role="CUSTOMER",
            marketer_type="CREATOR",
        )
        self.shop = Shop.objects.create(name="Test Shop", owner=self.shop_owner)
        self.product = Product.objects.create(
            name="Supplier Product X",
            shop=self.shop,
            supplier=self.supplier,
            price=Decimal("120.00"),
            supplier_price=Decimal("80.00"),
            minimum_wholesale_quantity=1,
        )
        self.order = Order.objects.create(
            order_number="ORD-TEST-PAYOUT-001",
            user=self.customer,
            shop=self.shop,
            status=Order.Status.DELIVERED,
            subtotal=Decimal("240.00"),
            total_amount=Decimal("240.00"),
            payment_method="santimpay",
            delivery_address="addr",
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            variant=None,
            product_name=self.product.name,
            sku=self.product.sku,
            price=Decimal("120.00"),
            quantity=2,
            total=Decimal("240.00"),
        )
        self.payment = Payment.objects.create(
            order=self.order,
            user=self.customer,
            amount=Decimal("240.00"),
            status=Payment.Status.COMPLETED,
            provider="SANTIMPAY",
            provider_reference="TXN-TEST-1",
            metadata={"merchant_id": self.shop_owner.merchant_id},
        )
        PaymentService(merchant_id=self.shop_owner.merchant_id).record_settlement_earnings(self.payment)

    @patch("payment.services.service.PaymentService._pay_user")
    def test_payout_executes_only_on_user_request(self, mock_pay_user):
        mock_pay_user.return_value = {
            "tx_id": "PYO-TEST-1",
            "method": "TELEBIRR",
            "account": "0911223344",
            "provider_response": {"id": "PAYOUT-REF-1"},
        }
        self.client.force_authenticate(self.supplier)

        response = self.client.post(
            "/payment/payouts/request/",
            {"confirm": True},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "COMPLETED")
        self.assertEqual(response.data["amount"], "160.00")
        self.assertEqual(response.data["provider_reference"], "PAYOUT-REF-1")
        self.assertEqual(mock_pay_user.call_count, 1)
        self.assertEqual(Earning.objects.filter(user=self.supplier, status=Earning.Status.AVAILABLE).count(), 0)

    @patch("payment.services.service.PaymentService._pay_user")
    def test_non_allocated_user_cannot_request_payout(self, mock_pay_user):
        self.client.force_authenticate(self.customer)
        response = self.client.post(
            "/payment/payouts/request/",
            {"confirm": True},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("No available earnings", response.data["detail"])
        self.assertEqual(mock_pay_user.call_count, 0)

    @patch("payment.services.service.PaymentService._pay_user")
    def test_user_can_list_payout_history(self, mock_pay_user):
        mock_pay_user.return_value = {
            "tx_id": "PYO-TEST-2",
            "method": "TELEBIRR",
            "account": "0911223344",
            "provider_response": {"id": "PAYOUT-REF-2"},
        }
        self.client.force_authenticate(self.supplier)
        create_resp = self.client.post(
            "/payment/payouts/request/",
            {"confirm": True},
            format="json",
        )
        self.assertEqual(create_resp.status_code, 201, create_resp.data)

        history_resp = self.client.get("/payment/payouts/history/")
        self.assertEqual(history_resp.status_code, 200, history_resp.data)
        self.assertEqual(len(history_resp.data["history"]), 1)
        self.assertEqual(history_resp.data["available_earnings"], "0.00")

    def test_settlement_is_blocked_until_order_delivered(self):
        self.order.status = Order.Status.PAID
        self.order.save(update_fields=["status", "updated_at"])
        self.payment.metadata = {"merchant_id": self.shop_owner.merchant_id}
        self.payment.save(update_fields=["metadata", "updated_at"])

        with self.assertRaises(PaymentServiceError):
            PaymentService(merchant_id=self.shop_owner.merchant_id).record_settlement_earnings(self.payment)


@override_settings(
    SANTIMPAY_PRIVATE_KEY="dummy-private-key",
    SANTIMPAY_TEST_BED=True,
    SANTIMPAY_NOTIFY_URL="http://localhost:8000/payment/webhook/santimpay/",
)
class PaymentLifecycleLogicTests(TestCase):
    def setUp(self):
        self.shop_owner = User.objects.create_user(
            email="owner_logic@shop.com",
            password="Pass123!",
            role="SHOP_OWNER",
            merchant_id="OWNER-MERCHANT-LOGIC",
            marketer_type="CREATOR",
            phone_number="0911001111",
        )
        self.customer = User.objects.create_user(
            email="customer_logic@shop.com",
            password="Pass123!",
            role="CUSTOMER",
            marketer_type="CREATOR",
        )
        self.shop = Shop.objects.create(name="Logic Shop", owner=self.shop_owner)
        self.category = Category.objects.create(name="Logic Category")
        self.product = Product.objects.create(
            name="Logic Product",
            shop=self.shop,
            category=self.category,
            price=Decimal("100.00"),
            supplier_price=Decimal("0.00"),
            minimum_wholesale_quantity=1,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            variant_name="Default",
            price=Decimal("100.00"),
            stock=5,
        )
        self.order = Order.objects.create(
            order_number="ORD-TEST-LOGIC-001",
            user=self.customer,
            shop=self.shop,
            status=Order.Status.PENDING,
            subtotal=Decimal("100.00"),
            total_amount=Decimal("100.00"),
            payment_method="santimpay",
            payment_reference="TXN-LOGIC-001",
            delivery_address="addr",
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            variant=self.variant,
            product_name=self.product.name,
            sku=self.product.sku,
            price=Decimal("100.00"),
            quantity=2,
            total=Decimal("200.00"),
        )
        self.payment = Payment.objects.create(
            order=self.order,
            user=self.customer,
            amount=Decimal("100.00"),
            status=Payment.Status.PENDING,
            provider="SANTIMPAY",
            provider_reference="TXN-LOGIC-001",
            metadata={"merchant_id": self.shop_owner.merchant_id},
        )
        self.service = PaymentService(merchant_id=self.shop_owner.merchant_id)

    def test_transition_matrix_allows_direct_pending_completion_and_failure(self):
        self.assertTrue(self.service._can_transition("PENDING", "COMPLETED"))
        self.assertTrue(self.service._can_transition("PENDING", "FAILED"))
        self.assertTrue(self.service._can_transition("PENDING", "PROCESSING"))
        self.assertFalse(self.service._can_transition("FAILED", "COMPLETED"))
        self.assertFalse(self.service._can_transition("REFUNDED", "COMPLETED"))

    @patch("payment.services.service.PaymentService.get_transaction_status")
    def test_sync_order_status_moves_pending_to_completed_on_success_gateway_status(self, mock_status):
        mock_status.return_value = {"status": "SUCCESS"}

        self.service.sync_order_status(self.order, tx_id=self.payment.provider_reference)

        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.COMPLETED)
        self.assertEqual(self.order.status, Order.Status.PAID)

    @patch("payment.services.service.PaymentService.get_transaction_status")
    def test_sync_order_status_moves_pending_to_failed_on_failure_gateway_status(self, mock_status):
        self.variant.stock = 3
        self.variant.save(update_fields=["stock", "updated_at"])
        mock_status.return_value = {"status": "FAILED"}

        self.service.sync_order_status(self.order, tx_id=self.payment.provider_reference)

        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.FAILED)
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertEqual(self.variant.stock, 5)

    @patch("payment.services.service.PaymentService.get_transaction_status")
    def test_sync_order_status_keeps_terminal_payment_state_unchanged(self, mock_status):
        self.payment.status = Payment.Status.FAILED
        self.payment.save(update_fields=["status", "updated_at"])
        mock_status.return_value = {"status": "SUCCESS"}

        self.service.sync_order_status(self.order, tx_id=self.payment.provider_reference)

        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.FAILED)
        self.assertEqual(self.order.status, Order.Status.PAID)

    def test_prepare_and_settle_split_payout_blocked_before_delivery(self):
        self.payment.status = Payment.Status.COMPLETED
        self.payment.save(update_fields=["status", "updated_at"])
        self.order.status = Order.Status.PAID
        self.order.save(update_fields=["status", "updated_at"])

        with self.assertRaises(PaymentServiceError):
            self.service.prepare_split_settlement(self.payment)
        with self.assertRaises(PaymentServiceError):
            self.service.settle_split_payout(self.payment)

    def test_delivery_signal_records_earnings_only_after_status_turns_delivered(self):
        self.payment.status = Payment.Status.COMPLETED
        self.payment.save(update_fields=["status", "updated_at"])

        self.order.status = Order.Status.PROCESSING
        self.order.save(update_fields=["status", "updated_at"])
        self.assertEqual(Earning.objects.filter(payment=self.payment).count(), 0)

        self.order.status = Order.Status.DELIVERED
        self.order.save(update_fields=["status", "updated_at"])
        self.assertGreater(Earning.objects.filter(payment=self.payment).count(), 0)
