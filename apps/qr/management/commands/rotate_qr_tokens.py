import uuid

from django.core.management.base import BaseCommand

from apps.qr.services import generate_table_qr
from apps.restaurants.models import Table


class Command(BaseCommand):
    help = "Invalidate and regenerate all table QR tokens"

    def handle(self, *args, **options):
        for table in Table.objects.all():
            table.qr_token = uuid.uuid4()
            table.qr_code.delete(save=False)
            table.save(update_fields=["qr_token"])
            generate_table_qr(table)
        self.stdout.write(self.style.SUCCESS("Rotated all QR tokens."))
