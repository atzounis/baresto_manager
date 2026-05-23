from django.db.models import Count

from apps.orders.models import OrderItem

# Orders in these statuses are not on the kitchen line for waiters.
_KITCHEN_EXCLUDED_ORDER_STATUSES = ("open", "paid", "cancelled")


def ready_item_counts_by_table_id(branch):
    """Map table_id → count of OrderItems in ``ready`` status (active sessions)."""
    if branch is None:
        return {}
    rows = (
        OrderItem.objects.filter(
            order__session__table__floor__branch=branch,
            order__session__is_active=True,
            order__is_deleted=False,
            is_deleted=False,
            status="ready",
        )
        .exclude(order__status__in=_KITCHEN_EXCLUDED_ORDER_STATUSES)
        .values("order__session__table_id")
        .annotate(count=Count("pk"))
    )
    return {row["order__session__table_id"]: row["count"] for row in rows}
