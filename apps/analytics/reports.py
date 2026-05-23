import csv
import io
from datetime import datetime, timedelta, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.orders.models import Bill, OrderItem
from apps.restaurants.models import TableSession

MAX_REPORT_DAYS = 366
DEFAULT_REPORT_DAYS = 7


def branch_timezone(branch):
    tz_name = branch.timezone if branch else settings.TIME_ZONE
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo(settings.TIME_ZONE)


def today_in_branch(branch):
    return timezone.now().astimezone(branch_timezone(branch)).date()


def parse_report_date_range(request, branch):
    """
    Parse ?from=YYYY-MM-DD&to=YYYY-MM-DD.
    Returns (date_from, date_to, error_message).
    """
    today = today_in_branch(branch)
    default_from = today - timedelta(days=DEFAULT_REPORT_DAYS - 1)

    raw_from = request.GET.get("from")
    raw_to = request.GET.get("to")

    if not raw_from and not raw_to:
        return default_from, today, None

    try:
        date_from = datetime.strptime(raw_from or raw_to, "%Y-%m-%d").date()
        date_to = datetime.strptime(raw_to or raw_from, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return default_from, today, _("Invalid date.")

    if date_from > date_to:
        date_from, date_to = date_to, date_from

    if date_to > today:
        return default_from, today, _("Cannot report on future dates.")

    if (date_to - date_from).days + 1 > MAX_REPORT_DAYS:
        return default_from, today, _("Date range cannot exceed %(days)s days.") % {"days": MAX_REPORT_DAYS}

    return date_from, date_to, None


def range_datetimes(date_from, date_to, tz):
    start = datetime.combine(date_from, time.min, tzinfo=tz)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=tz)
    return start, end


def paid_bills_queryset(branch, start, end):
    return (
        Bill.objects.filter(
            order__session__table__floor__branch=branch,
            is_paid=True,
            paid_at__gte=start,
            paid_at__lt=end,
        )
        .select_related(
            "order__session__table",
            "order__waiter__user",
        )
        .order_by("-paid_at")
    )


def report_summary(branch, start, end):
    bills = paid_bills_queryset(branch, start, end)
    agg = bills.aggregate(revenue=Sum("total"), orders=Count("id"))
    revenue = agg["revenue"] or Decimal("0")
    orders_count = agg["orders"] or 0
    sessions_count = TableSession.objects.filter(
        table__floor__branch=branch,
        opened_at__gte=start,
        opened_at__lt=end,
    ).count()
    avg_ticket = (revenue / orders_count).quantize(Decimal("0.01")) if orders_count else Decimal("0")
    return {
        "revenue_total": revenue,
        "orders_count": orders_count,
        "sessions_count": sessions_count,
        "avg_ticket": avg_ticket,
    }


def daily_series(branch, date_from, date_to, tz, start, end):
    """Daily revenue, orders, and sessions for charts (includes zero days)."""
    revenue_rows = (
        paid_bills_queryset(branch, start, end)
        .annotate(day=TruncDate("paid_at", tzinfo=tz))
        .values("day")
        .annotate(revenue=Sum("total"), orders=Count("id"))
    )
    revenue_by_day = {row["day"]: row for row in revenue_rows}

    session_rows = (
        TableSession.objects.filter(
            table__floor__branch=branch,
            opened_at__gte=start,
            opened_at__lt=end,
        )
        .annotate(day=TruncDate("opened_at", tzinfo=tz))
        .values("day")
        .annotate(sessions=Count("id"))
    )
    sessions_by_day = {row["day"]: row["sessions"] for row in session_rows}

    labels = []
    revenue = []
    orders = []
    sessions = []
    day = date_from
    while day <= date_to:
        labels.append(day.isoformat())
        row = revenue_by_day.get(day, {})
        revenue.append(float(row.get("revenue") or 0))
        orders.append(row.get("orders") or 0)
        sessions.append(sessions_by_day.get(day, 0))
        day += timedelta(days=1)
    return {
        "labels": labels,
        "revenue": revenue,
        "orders": orders,
        "sessions": sessions,
    }


def top_items(branch, start, end, limit=10):
    return list(
        OrderItem.objects.filter(
            order__session__table__floor__branch=branch,
            order__bill__is_paid=True,
            order__bill__paid_at__gte=start,
            order__bill__paid_at__lt=end,
            is_deleted=False,
        )
        .values("menu_item__name")
        .annotate(qty=Sum("quantity"))
        .order_by("-qty")[:limit]
    )


def top_items_chart(top_items_rows, limit=8):
    rows = top_items_rows[:limit]
    return {
        "labels": [r["menu_item__name"] for r in rows],
        "quantities": [r["qty"] for r in rows],
    }


def build_reports_csv(branch, date_from, date_to, tz):
    start, end = range_datetimes(date_from, date_to, tz)
    bills = paid_bills_queryset(branch, start, end).prefetch_related(
        "order__items__menu_item",
        "order__items__modifiers",
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "paid_date",
        "paid_at",
        "order_id",
        "table",
        "waiter",
        "item_name",
        "quantity",
        "unit_price",
        "line_total",
        "order_subtotal",
        "order_tax",
        "order_discount",
        "order_total",
        "payment_method",
    ])

    for bill in bills:
        paid_local = bill.paid_at.astimezone(tz) if bill.paid_at else None
        paid_date = paid_local.date().isoformat() if paid_local else ""
        paid_at = paid_local.isoformat(timespec="seconds") if paid_local else ""
        table = str(bill.order.session.table)
        waiter = ""
        if bill.order.waiter and bill.order.waiter.user:
            waiter = bill.order.waiter.user.get_full_name() or bill.order.waiter.user.username
        items = bill.order.items.filter(is_deleted=False).select_related("menu_item")
        if not items.exists():
            writer.writerow([
                paid_date,
                paid_at,
                bill.order_id,
                table,
                waiter,
                "",
                "",
                "",
                "",
                bill.subtotal,
                bill.tax,
                bill.discount,
                bill.total,
                bill.payment_method,
            ])
            continue
        for item in items:
            writer.writerow([
                paid_date,
                paid_at,
                bill.order_id,
                table,
                waiter,
                item.menu_item.name,
                item.quantity,
                item.unit_price,
                item.line_total,
                bill.subtotal,
                bill.tax,
                bill.discount,
                bill.total,
                bill.payment_method,
            ])

    filename = f"baresto_report_{date_from.isoformat()}_{date_to.isoformat()}.csv"
    return "\ufeff" + buffer.getvalue(), filename
