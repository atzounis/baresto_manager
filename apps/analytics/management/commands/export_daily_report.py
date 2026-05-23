import csv
from datetime import date

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from apps.orders.models import Bill


class Command(BaseCommand):
    help = "Export CSV of a day's paid bills"

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, default=str(date.today()))
        parser.add_argument("--output", type=str, default="daily_report.csv")

    def handle(self, *args, **options):
        day = date.fromisoformat(options["date"])
        bills = Bill.objects.filter(is_paid=True, paid_at__date=day).select_related("order")
        path = options["output"]
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["order_id", "subtotal", "tax", "discount", "total", "payment_method", "paid_at"])
            for b in bills:
                writer.writerow([
                    b.order_id,
                    b.subtotal,
                    b.tax,
                    b.discount,
                    b.total,
                    b.payment_method,
                    b.paid_at,
                ])
        total = bills.aggregate(s=Sum("total"))["s"] or 0
        self.stdout.write(self.style.SUCCESS(f"Wrote {bills.count()} rows to {path} (total {total})"))
