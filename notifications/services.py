import json
import logging
from typing import Any, Dict, Iterable, Optional

from django.conf import settings
from django.db import transaction

from .models import DeviceToken, Notification

logger = logging.getLogger(__name__)


class NotificationService:
    _firebase_app_initialized = False

    @classmethod
    def _init_firebase(cls) -> bool:
        if cls._firebase_app_initialized:
            return True
        try:
            import firebase_admin
            from firebase_admin import credentials

            if firebase_admin._apps:
                cls._firebase_app_initialized = True
                return True

            service_account_path = getattr(settings, "FCM_SERVICE_ACCOUNT_FILE", "")
            service_account_json = getattr(settings, "FCM_SERVICE_ACCOUNT_JSON", "")
            project_id = getattr(settings, "FCM_PROJECT_ID", "")

            if service_account_json:
                cred = credentials.Certificate(json.loads(service_account_json))
                firebase_admin.initialize_app(cred, {"projectId": project_id} if project_id else None)
            elif service_account_path:
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred, {"projectId": project_id} if project_id else None)
            else:
                logger.info("FCM credentials are not configured. Push sending is disabled.")
                return False

            cls._firebase_app_initialized = True
            return True
        except Exception:
            logger.exception("Failed to initialize Firebase app")
            return False

    @classmethod
    @transaction.atomic
    def notify(
        cls,
        *,
        user,
        notification_type: str,
        title: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        payload = payload or {}
        notification = Notification.objects.create(
            user=user,
            type=notification_type,
            title=title,
            message=message,
            payload=payload,
        )
        try:
            cls._send_push_to_user(user=user, title=title, message=message, payload=payload)
        except Exception:
            logger.exception("Push send failed for user=%s type=%s", user.id, notification_type)
        return notification

    @classmethod
    def _send_push_to_user(cls, *, user, title: str, message: str, payload: Dict[str, Any]) -> None:
        if not cls._init_firebase():
            return
        tokens = list(DeviceToken.objects.filter(user=user, is_active=True).values_list("token", flat=True))
        if not tokens:
            return

        import firebase_admin
        from firebase_admin import messaging
        from firebase_admin.exceptions import FirebaseError

        for token in tokens:
            try:
                msg = messaging.Message(
                    notification=messaging.Notification(title=title, body=message),
                    data={k: str(v) for k, v in payload.items()},
                    token=token,
                )
                messaging.send(msg)
            except FirebaseError as exc:
                error_code = getattr(exc, "code", "") or str(exc)
                # Deactivate known invalid token scenarios.
                if "registration-token-not-registered" in error_code or "invalid-argument" in error_code:
                    DeviceToken.objects.filter(token=token).update(is_active=False)
                logger.warning("FCM send failed token=%s code=%s", token[:12], error_code)
            except Exception:
                logger.exception("Unexpected FCM error token=%s", token[:12])


class NotificationTemplates:
    @staticmethod
    def payment_success(order):
        return (
            "Payment Successful",
            f"Your order #{order.order_number} has been confirmed.",
            {
                "type": "payment_success",
                "entity_id": str(order.id),
                "entity_type": "order",
                "order_id": str(order.id),
            },
        )

    @staticmethod
    def order_shipped(order):
        return (
            "Order Shipped",
            f"Your order #{order.order_number} is on the way.",
            {
                "type": "order_shipped",
                "entity_id": str(order.id),
                "entity_type": "order",
                "order_id": str(order.id),
            },
        )

    @staticmethod
    def order_delivered(order):
        return (
            "Order Delivered",
            f"Your order #{order.order_number} has been delivered.",
            {
                "type": "order_delivered",
                "entity_id": str(order.id),
                "entity_type": "order",
                "order_id": str(order.id),
            },
        )

    @staticmethod
    def new_order(order):
        return (
            "New Order",
            f"You received a new order #{order.order_number}.",
            {
                "type": "new_order",
                "entity_id": str(order.id),
                "entity_type": "order",
                "order_id": str(order.id),
            },
        )

    @staticmethod
    def payment_confirmed(order):
        return (
            "Payment Confirmed",
            f"Payment received for order #{order.order_number}.",
            {
                "type": "payment_confirmed",
                "entity_id": str(order.id),
                "entity_type": "order",
                "order_id": str(order.id),
            },
        )

    @staticmethod
    def product_sold(order, product):
        return (
            "Product Sold",
            f"Your product {product.name} was sold.",
            {
                "type": "product_sold",
                "entity_id": str(order.id),
                "entity_type": "order",
                "order_id": str(order.id),
                "product_id": str(product.id),
            },
        )

    @staticmethod
    def commission_created(order, commission):
        return (
            "Commission Created",
            f"You earned commission for order #{order.order_number}.",
            {
                "type": "commission_created",
                "entity_id": str(commission.id),
                "entity_type": "commission",
                "commission_id": str(commission.id),
                "order_id": str(order.id),
            },
        )

    @staticmethod
    def commission_approved(order, commission):
        return (
            "Commission Approved",
            f"Your commission for order #{order.order_number} is approved.",
            {
                "type": "commission_approved",
                "entity_id": str(commission.id),
                "entity_type": "commission",
                "commission_id": str(commission.id),
                "order_id": str(order.id),
            },
        )
