from django.test import TestCase
from rest_framework.test import APIClient

from account.models import User
from .models import DeviceToken, Notification


class NotificationsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="user@shikela.com",
            password="Pass123!",
            role="CUSTOMER",
            marketer_type="CREATOR",
        )
        self.other = User.objects.create_user(
            email="other@shikela.com",
            password="Pass123!",
            role="CUSTOMER",
            marketer_type="CREATOR",
        )
        self.client.force_authenticate(self.user)

    def test_device_token_upsert_and_reassign(self):
        resp1 = self.client.post(
            "/api/notifications/device-token/",
            {"token": "token-123", "device_type": "web"},
            format="json",
        )
        self.assertEqual(resp1.status_code, 200, resp1.data)
        token_row = DeviceToken.objects.get(token="token-123")
        self.assertEqual(token_row.user_id, self.user.id)
        self.assertTrue(token_row.is_active)

        self.client.force_authenticate(self.other)
        resp2 = self.client.post(
            "/api/notifications/device-token/",
            {"token": "token-123", "device_type": "android"},
            format="json",
        )
        self.assertEqual(resp2.status_code, 200, resp2.data)
        token_row.refresh_from_db()
        self.assertEqual(token_row.user_id, self.other.id)
        self.assertEqual(token_row.device_type, "android")

    def test_device_token_deactivate(self):
        DeviceToken.objects.create(user=self.user, token="token-a", device_type="web", is_active=True)
        resp = self.client.delete(
            "/api/notifications/device-token/",
            {"token": "token-a"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["deactivated"], 1)
        self.assertFalse(DeviceToken.objects.get(token="token-a").is_active)

    def test_notification_read_endpoints(self):
        note1 = Notification.objects.create(
            user=self.user,
            type="payment_success",
            title="Payment Successful",
            message="Order paid",
            payload={"type": "payment_success", "entity_id": "1", "entity_type": "order"},
        )
        note2 = Notification.objects.create(
            user=self.user,
            type="order_shipped",
            title="Order Shipped",
            message="On the way",
            payload={"type": "order_shipped", "entity_id": "1", "entity_type": "order"},
        )

        list_resp = self.client.get("/api/notifications/")
        self.assertEqual(list_resp.status_code, 200, list_resp.data)
        self.assertEqual(list_resp.data["count"], 2)

        read_one = self.client.patch(f"/api/notifications/{note1.id}/read/", {}, format="json")
        self.assertEqual(read_one.status_code, 200, read_one.data)
        note1.refresh_from_db()
        self.assertTrue(note1.is_read)

        read_all = self.client.post("/api/notifications/mark-all-read/", {}, format="json")
        self.assertEqual(read_all.status_code, 200, read_all.data)
        note2.refresh_from_db()
        self.assertTrue(note2.is_read)
