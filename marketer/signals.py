from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from order.models import Order
from .services import MarketerCommissionService
from notifications.services import NotificationService, NotificationTemplates


@receiver(pre_save, sender=Order)
def _cache_previous_order_status(sender, instance: Order, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    previous = Order.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    instance._previous_status = previous


@receiver(post_save, sender=Order)
def _approve_commissions_on_delivery(sender, instance: Order, **kwargs):
    previous = getattr(instance, "_previous_status", None)
    if previous == instance.status:
        return
    if instance.status == Order.Status.DELIVERED:
        commissions = MarketerCommissionService.approve_for_order(instance)
        for commission in commissions:
            try:
                title, message, payload = NotificationTemplates.commission_approved(instance, commission)
                NotificationService.notify(
                    user=commission.contract.marketer,
                    notification_type="commission_approved",
                    title=title,
                    message=message,
                    payload=payload,
                )
            except Exception:
                # Never break order status updates because of notifications.
                pass
