from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from django.db import transaction

from account.badge_logic import resolve_badge
from order.models import Order
from notifications.services import NotificationService, NotificationTemplates

from .models import CourierPartner, Shipment


class LogisticsError(Exception):
    pass


@dataclass(frozen=True)
class ShipmentCreateResult:
    shipment_id: str
    tracking_id: str
    status: str
    raw_response: Dict[str, Any]


class BaseCourierAdapter:
    provider_code: str = "base"

    def __init__(self, courier: CourierPartner):
        self.courier = courier

    def create_shipment(self, shipment: Shipment) -> ShipmentCreateResult:  # pragma: no cover - interface
        raise NotImplementedError

    def normalize_status(self, raw_status: str) -> str:
        status = (raw_status or "").strip().upper()
        mapping = {
            "CREATED": Shipment.Status.CREATED,
            "PICKED_UP": Shipment.Status.PICKED_UP,
            "PICKUP": Shipment.Status.PICKED_UP,
            "IN_TRANSIT": Shipment.Status.IN_TRANSIT,
            "TRANSIT": Shipment.Status.IN_TRANSIT,
            "OUT_FOR_DELIVERY": Shipment.Status.OUT_FOR_DELIVERY,
            "DELIVERED": Shipment.Status.DELIVERED,
            "FAILED": Shipment.Status.FAILED,
            "CANCELLED": Shipment.Status.CANCELLED,
        }
        return mapping.get(status, Shipment.Status.PENDING)


class HudhudAdapter(BaseCourierAdapter):
    provider_code = "hudhud"

    def create_shipment(self, shipment: Shipment) -> ShipmentCreateResult:
        payload = {
            "reference": str(shipment.id),
            "order_number": shipment.order.order_number,
            "delivery_address": shipment.order.delivery_address,
            "customer_phone": getattr(shipment.order.user, "phone_number", ""),
            "amount": float(shipment.order.total_amount),
        }

        # If no API config exists, keep a deterministic mock flow for local/dev.
        if not self.courier.api_base_url:
            tracking = f"HD-{uuid.uuid4().hex[:10].upper()}"
            return ShipmentCreateResult(
                shipment_id=f"MOCK-{uuid.uuid4().hex[:12].upper()}",
                tracking_id=tracking,
                status=Shipment.Status.CREATED,
                raw_response={"mock": True, "tracking_id": tracking},
            )

        headers = {"Content-Type": "application/json"}
        if self.courier.api_key:
            headers["Authorization"] = f"Bearer {self.courier.api_key}"

        response = requests.post(
            f"{self.courier.api_base_url.rstrip('/')}/shipments",
            json=payload,
            headers=headers,
            timeout=20,
        )
        if not response.ok:
            try:
                details = response.json()
            except Exception:
                details = {"text": response.text}
            raise LogisticsError(f"Courier create shipment failed: {details}")

        data = response.json()
        return ShipmentCreateResult(
            shipment_id=str(data.get("shipment_id") or data.get("id") or ""),
            tracking_id=str(data.get("tracking_id") or data.get("trackingId") or ""),
            status=self.normalize_status(str(data.get("status") or "CREATED")),
            raw_response=data,
        )


def _adapter_for(courier: CourierPartner) -> BaseCourierAdapter:
    code = (courier.provider_code or "").lower()
    if code == "hudhud":
        return HudhudAdapter(courier)
    # Fallback to Hudhud-compatible shape
    return HudhudAdapter(courier)


def select_active_courier() -> CourierPartner:
    courier = CourierPartner.objects.filter(is_active=True).order_by("priority", "created_at").first()
    if not courier:
        raise LogisticsError("No active courier partner configured")
    return courier


@transaction.atomic
def create_shipment_for_order(order: Order) -> Shipment:
    if hasattr(order, "shipment"):
        return order.shipment

    courier = select_active_courier()
    shipment = Shipment.objects.create(
        order=order,
        courier=courier,
        status=Shipment.Status.PENDING,
    )

    adapter = _adapter_for(courier)
    result = adapter.create_shipment(shipment)

    shipment.external_shipment_id = result.shipment_id
    shipment.external_tracking_id = result.tracking_id
    shipment.status = result.status or Shipment.Status.CREATED
    shipment.last_event = "shipment_created"
    shipment.last_payload = result.raw_response
    shipment.save(
        update_fields=[
            "external_shipment_id",
            "external_tracking_id",
            "status",
            "last_event",
            "last_payload",
            "updated_at",
        ]
    )
    return shipment


@transaction.atomic
def update_shipment_status(shipment: Shipment, new_status: str, payload: Optional[Dict[str, Any]] = None) -> Shipment:
    payload = payload or {}
    shipment.status = new_status
    shipment.last_event = "status_update"
    shipment.last_payload = payload
    shipment.save(update_fields=["status", "last_event", "last_payload", "updated_at"])

    order = shipment.order
    if new_status == Shipment.Status.PICKED_UP and order.status in {Order.Status.PAID, Order.Status.CONFIRMED}:
        order.status = Order.Status.CONFIRMED
        order.save(update_fields=["status", "updated_at"])
    elif new_status in {Shipment.Status.IN_TRANSIT, Shipment.Status.OUT_FOR_DELIVERY}:
        if order.status != Order.Status.DELIVERED:
            order.status = Order.Status.SHIPPED if new_status == Shipment.Status.OUT_FOR_DELIVERY else Order.Status.PROCESSING
            order.save(update_fields=["status", "updated_at"])
            if order.status == Order.Status.SHIPPED:
                try:
                    title, message, payload = NotificationTemplates.order_shipped(order)
                    NotificationService.notify(
                        user=order.user,
                        notification_type="order_shipped",
                        title=title,
                        message=message,
                        payload=payload,
                    )
                except Exception:
                    pass
    elif new_status == Shipment.Status.DELIVERED:
        if order.status != Order.Status.DELIVERED:
            order.status = Order.Status.DELIVERED
            order.save(update_fields=["status", "updated_at"])
            try:
                title, message, payload = NotificationTemplates.order_delivered(order)
                NotificationService.notify(
                    user=order.user,
                    notification_type="order_delivered",
                    title=title,
                    message=message,
                    payload=payload,
                )
            except Exception:
                pass
        # Badge refresh on successful delivery completion
        resolve_badge(order.user, persist=True)
        resolve_badge(order.shop.owner, persist=True)
    elif new_status in {Shipment.Status.FAILED, Shipment.Status.CANCELLED}:
        if order.status != Order.Status.DELIVERED:
            order.status = Order.Status.CANCELLED
            order.save(update_fields=["status", "updated_at"])

    return shipment


@transaction.atomic
def process_courier_webhook(provider_code: str, payload: Dict[str, Any]) -> Shipment:
    tracking = str(payload.get("tracking_id") or payload.get("trackingId") or "").strip()
    shipment_id = str(payload.get("shipment_id") or payload.get("shipmentId") or "").strip()
    raw_status = str(payload.get("status") or "").strip()
    if not raw_status:
        raise LogisticsError("Missing status")

    courier = CourierPartner.objects.filter(provider_code__iexact=provider_code, is_active=True).first()
    if not courier:
        raise LogisticsError("Courier partner not found")

    shipment = None
    if tracking:
        shipment = Shipment.objects.filter(courier=courier, external_tracking_id=tracking).select_related("order", "order__shop__owner", "order__user").first()
    if not shipment and shipment_id:
        shipment = Shipment.objects.filter(courier=courier, external_shipment_id=shipment_id).select_related("order", "order__shop__owner", "order__user").first()
    if not shipment:
        raise LogisticsError("Shipment not found")

    adapter = _adapter_for(courier)
    normalized = adapter.normalize_status(raw_status)
    return update_shipment_status(shipment, normalized, payload=payload)
