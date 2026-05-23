from django.core.management.base import BaseCommand

from apps.qr.services import generate_table_qr
from apps.restaurants.models import Table


class Command(BaseCommand):
    help = "Regenerate QR PNGs for all tables"

    def handle(self, *args, **options):
        count = 0
        for table in Table.objects.all():
            generate_table_qr(table)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Generated {count} QR codes."))
