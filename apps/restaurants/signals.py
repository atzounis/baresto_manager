from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.qr.services import generate_table_qr

from .models import Table


@receiver(post_save, sender=Table)
def table_qr_on_save(sender, instance, created, **kwargs):
    if created or not instance.qr_code:
        generate_table_qr(instance)
