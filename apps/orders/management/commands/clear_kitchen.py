from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.orders.models import Order
from apps.orders.services import clear_kitchen_ticket
from apps.realtime import broadcast_table_update
from apps.restaurants.models import TableSession

KITCHEN_STATUSES = ["confirmed", "preparing", "partially_ready", "ready"]


class Command(BaseCommand):
    help = "Clear stuck orders from the kitchen display (mark paid/served and broadcast)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--closed-sessions-only",
            action="store_true",
            help="Only clear tickets for tables that are already closed (default: clear all kitchen tickets).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List matching orders without changing them.",
        )

    def handle(self, *args, **options):
        qs = Order.objects.filter(status__in=KITCHEN_STATUSES, is_deleted=False).select_related(
            "session__table"
        )
        if options["closed_sessions_only"]:
            qs = qs.filter(session__is_active=False)

        orders = list(qs.order_by("pk"))
        if not orders:
            self.stdout.write("No kitchen tickets to clear.")
            return

        if options["dry_run"]:
            for order in orders:
                self.stdout.write(
                    f"  Would clear #{order.pk} — {order.session.table} "
                    f"({order.status}, session active={order.session.is_active})"
                )
            self.stdout.write(self.style.WARNING(f"Dry run: {len(orders)} order(s)."))
            return

        for order in orders:
            clear_kitchen_ticket(order)
            self.stdout.write(
                f"  Cleared #{order.pk} — {order.session.table} (was {order.status})"
            )

        self.stdout.write(self.style.SUCCESS(f"Cleared {len(orders)} kitchen ticket(s)."))
        self._close_orphan_sessions()

    def _close_orphan_sessions(self):
        """Close open sessions that have no unfinished orders and free the table."""
        open_statuses = ["open", "confirmed", "preparing", "partially_ready", "ready", "bill_requested"]
        closed = 0
        for session in TableSession.objects.filter(is_active=True).select_related("table"):
            if session.orders.filter(is_deleted=False, status__in=open_statuses).exists():
                continue
            session.is_active = False
            session.closed_at = timezone.now()
            session.save(update_fields=["is_active", "closed_at", "updated_at"])
            table = session.table
            if table.status != "free":
                table.status = "free"
                table.save(update_fields=["status"])
                broadcast_table_update(table)
            closed += 1
        if closed:
            self.stdout.write(self.style.SUCCESS(f"Closed {closed} orphan table session(s)."))
