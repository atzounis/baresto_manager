from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.orders.models import Order


class Command(BaseCommand):
    help = "Auto-close orders open longer than N hours"

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=8)

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=options["hours"])
        qs = Order.objects.filter(
            status__in=["open", "confirmed", "preparing"],
            created_at__lt=cutoff,
        )
        count = qs.update(status="cancelled", closed_at=timezone.now())
        self.stdout.write(self.style.SUCCESS(f"Closed {count} stale orders."))
