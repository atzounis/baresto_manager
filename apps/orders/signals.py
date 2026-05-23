from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.realtime import broadcast_order_event

from .models import Order


@receiver(post_save, sender=Order)
def order_broadcast(sender, instance, created, **kwargs):
    if created:
        broadcast_order_event(instance, event="order.created")
