from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from account.models import PaymentMethod, User
from account.serializers import PaymentMethodSerializer


class UserModelTests(TestCase):
    def test_create_user_hashes_password(self):
        user = User.objects.create_user(
            email="user@example.com",
            password="Pass123!",
            marketer_type="CREATOR",
        )

        self.assertNotEqual(user.password, "Pass123!")
        self.assertTrue(user.check_password("Pass123!"))

    def test_create_user_requires_email(self):
        with self.assertRaisesMessage(ValueError, "Users must have an email"):
            User.objects.create_user(
                email="",
                password="Pass123!",
                marketer_type="CREATOR",
            )


class PaymentMethodSerializerTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.shop_owner = User.objects.create_user(
            email="owner@example.com",
            password="Pass123!",
            role="SHOP_OWNER",
            marketer_type="CREATOR",
        )
        self.customer = User.objects.create_user(
            email="customer@example.com",
            password="Pass123!",
            role="CUSTOMER",
            marketer_type="CREATOR",
        )

    def test_bank_payment_requires_account_number(self):
        serializer = PaymentMethodSerializer(
            data={"payment_type": "BANK", "phone_number": "0911223344"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("account_number", serializer.errors)

    def test_mobile_payment_requires_phone_number(self):
        serializer = PaymentMethodSerializer(
            data={"payment_type": "TELEBIRR", "account_number": "123456"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("phone_number", serializer.errors)

    def test_serializer_assigns_shop_owner_from_request_user(self):
        request = self.factory.post("/auth/create-payment-method/")
        request.user = self.shop_owner
        serializer = PaymentMethodSerializer(
            data={"payment_type": "BANK", "account_number": "100200300"},
            context={"request": request},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        payment_method = serializer.save()

        self.assertEqual(payment_method.shop_owner_id, self.shop_owner.id)
        self.assertEqual(PaymentMethod.objects.count(), 1)

    def test_non_shop_owner_cannot_create_payment_method(self):
        request = self.factory.post("/auth/create-payment-method/")
        request.user = self.customer
        serializer = PaymentMethodSerializer(
            data={"payment_type": "BANK", "account_number": "100200300"},
            context={"request": request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        with self.assertRaises(ValidationError):
            serializer.save()
