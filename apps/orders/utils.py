from django.db.models import Count
from django.utils.translation import gettext_lazy as _

from apps.orders.models import OrderItem

# Orders in these statuses are not on the kitchen line for waiters.
_KITCHEN_EXCLUDED_ORDER_STATUSES = ("open", "paid", "cancelled")


class TableCloseBlocked(Exception):
    """Raised when a table session cannot be closed yet."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


def close_table_blockers(session):
    """
    Return blockers as (code, message) pairs. Empty list means the table may be closed.
    """
    blockers = []

    if OrderItem.objects.filter(
        order__session=session,
        order__status="open",
        order__is_deleted=False,
        is_deleted=False,
    ).exists():
        blockers.append(
            ("unsent_items", _("Send all items to the kitchen before closing the table."))
        )

    if OrderItem.objects.filter(
        order__session=session,
        order__is_deleted=False,
        is_deleted=False,
        status__in=("pending", "preparing"),
    ).exclude(order__status__in=_KITCHEN_EXCLUDED_ORDER_STATUSES).exists():
        blockers.append(
            ("kitchen_pending", _("Wait until the kitchen finishes preparing all items."))
        )

    if OrderItem.objects.filter(
        order__session=session,
        order__is_deleted=False,
        is_deleted=False,
        status="ready",
    ).exclude(order__status__in=_KITCHEN_EXCLUDED_ORDER_STATUSES).exists():
        blockers.append(
            ("ready_pending", _("Deliver all ready items before closing the table."))
        )

    return blockers


def can_close_table_session(session):
    return not close_table_blockers(session)


def close_table_blocked_message(session):
    blockers = close_table_blockers(session)
    if not blockers:
        return ""
    return str(blockers[0][1])


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
