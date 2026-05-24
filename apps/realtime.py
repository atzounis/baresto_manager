import logging
import time

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache

logger = logging.getLogger(__name__)


def _group_send(group_name, message_type, payload):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        group_name,
        {"type": message_type, "payload": payload},
    )


def broadcast_order_event(order, event="order.updated", extra=None):
    branch_id = order.branch.id
    payload = {
        "event": event,
        "order_id": order.pk,
        "table": str(order.session.table),
        "status": order.status,
        "is_priority": order.is_priority,
        **(extra or {}),
    }
    _group_send(f"kitchen.{branch_id}", "kitchen.message", payload)
    _group_send(f"dashboard.{branch_id}", "dashboard.message", payload)
    if order.waiter_id:
        _group_send(f"waiter.{order.waiter_id}", "waiter.message", payload)
    _group_send(f"table.{order.session.table_id}", "table.message", payload)


def _waiter_staff_ids(order):
    """Staff who should get kitchen-ready alerts for this order."""
    ids = []
    if order.waiter_id:
        ids.append(order.waiter_id)
    table = order.session.table
    if table.assigned_to_id and table.assigned_to_id not in ids:
        ids.append(table.assigned_to_id)
    return ids


def _cache_waiter_alert(branch_id, payload):
    """Store for HTTP poll fallback (mobile browsers often drop WebSockets)."""
    key = f"waiter_alerts:branch:{branch_id}"
    try:
        alerts = cache.get(key) or []
        alerts.append(payload)
        cache.set(key, alerts[-30:], timeout=600)
    except Exception:
        logger.exception("Failed to cache waiter alert for branch %s", branch_id)


def _send_waiter_alert(order, payload):
    branch_id = order.branch.id
    restaurant_id = order.branch.restaurant_id
    # WebSocket first — must not be blocked by cache/Redis failures.
    _group_send(f"waiters.branch.{branch_id}", "waiter.message", payload)
    _group_send(f"waiters.restaurant.{restaurant_id}", "waiter.message", payload)
    for staff_id in _waiter_staff_ids(order):
        _group_send(f"waiter.{staff_id}", "waiter.message", payload)
    _cache_waiter_alert(branch_id, payload)


def broadcast_waiter_kitchen_ready(order, *, item_name=None, order_fully_ready=False):
    """Sound/notification alert for waiters when kitchen advances items to ready."""
    table_label = str(order.session.table)
    base = {
        "order_id": order.pk,
        "table": table_label,
        "table_id": order.session.table_id,
        "order_status": order.status,
    }

    if item_name:
        payload = {
            **base,
            "event": "order.item_ready",
            "item_name": item_name,
            "message": f"{table_label}: {item_name}",
        }
        _send_waiter_alert(order, payload)

    if order_fully_ready:
        payload = {
            **base,
            "event": "order.ready",
            "message": table_label,
            "alert": "order_ready",
        }
        _send_waiter_alert(order, payload)


def _cache_kitchen_alert(branch_id, payload):
    """Store for HTTP poll fallback on kitchen display screens."""
    key = f"kitchen_alerts:branch:{branch_id}"
    try:
        alerts = cache.get(key) or []
        alerts.append(payload)
        cache.set(key, alerts[-30:], timeout=600)
    except Exception:
        logger.exception("Failed to cache kitchen alert for branch %s", branch_id)


def pop_branch_kitchen_alerts(branch_id):
    key = f"kitchen_alerts:branch:{branch_id}"
    try:
        alerts = cache.get(key) or []
        cache.delete(key)
        return alerts
    except Exception:
        logger.exception("Failed to read kitchen alerts for branch %s", branch_id)
        return []


def broadcast_kitchen_new_ticket(order):
    """Sound/modal alert on KDS when a waiter sends an order to the kitchen."""
    branch_id = order.branch.id
    table = order.session.table
    items_qs = order.items.filter(is_deleted=False).select_related("menu_item")
    items = list(items_qs)
    item_count = sum(row.quantity for row in items)
    item_lines = [f"{row.quantity}× {row.menu_item.name}" for row in items[:8]]
    remaining = len(items) - len(item_lines)
    if remaining > 0:
        item_lines.append(f"+{remaining}")

    notes = (order.notes or "").strip()
    payload = {
        "event": "order.new_ticket",
        "order_id": order.pk,
        "table": str(table),
        "table_id": table.pk,
        "floor": table.floor.name if table.floor_id else "",
        "item_count": item_count,
        "item_lines": item_lines,
        "is_priority": order.is_priority,
        "sent_at": time.time(),
    }
    if notes:
        payload["notes"] = notes
    _group_send(f"kitchen.{branch_id}", "kitchen.message", payload)
    _cache_kitchen_alert(branch_id, payload)


def pop_branch_waiter_alerts(branch_id):
    key = f"waiter_alerts:branch:{branch_id}"
    try:
        alerts = cache.get(key) or []
        cache.delete(key)
        return alerts
    except Exception:
        logger.exception("Failed to read waiter alerts for branch %s", branch_id)
        return []


def peek_table_closed_alerts(branch_id, since=0):
    key = f"table_closed_alerts:branch:{branch_id}"
    try:
        alerts = cache.get(key) or []
        return [a for a in alerts if a.get("closed_at", 0) > since]
    except Exception:
        logger.exception("Failed to read table closed alerts for branch %s", branch_id)
        return []


def _cache_table_closed_alert(branch_id, payload):
    key = f"table_closed_alerts:branch:{branch_id}"
    try:
        alerts = cache.get(key) or []
        alerts.append(payload)
        cache.set(key, alerts[-20:], timeout=600)
    except Exception:
        logger.exception("Failed to cache table closed alert for branch %s", branch_id)


def broadcast_table_closed(order, table):
    """Notify all staff devices when a waiter closes a table (tables screen + receipt prompt)."""
    from apps.orders.models import Bill

    branch = table.branch
    branch_id = branch.id
    restaurant_id = branch.restaurant_id
    bill = Bill.objects.filter(order_id=order.pk).first() if order else None

    payload = {
        "event": "table.closed",
        "table_id": table.pk,
        "table": str(table),
        "table_label": table.label or f"T{table.number}",
        "floor": table.floor.name if table.floor_id else "",
        "order_id": order.pk if order else None,
        "bill_total": str(bill.total) if bill else None,
        "payment_method": bill.payment_method if bill else "cash",
        "can_print_receipt": bill is not None,
        "closed_at": time.time(),
    }

    _group_send(f"waiters.branch.{branch_id}", "waiter.message", payload)
    _group_send(f"waiters.restaurant.{restaurant_id}", "waiter.message", payload)
    if table.assigned_to_id:
        _group_send(f"waiter.{table.assigned_to_id}", "waiter.message", payload)
    _cache_table_closed_alert(branch_id, payload)


def broadcast_table_update(table):
    branch_id = table.branch.id
    payload = {
        "event": "table.updated",
        "table_id": table.pk,
        "status": table.status,
        "label": str(table),
    }
    _group_send(f"dashboard.{branch_id}", "dashboard.message", payload)
    _group_send(f"table.{table.pk}", "table.message", payload)


def broadcast_guest_waiter_call(*, branch_id, restaurant_id, table=None):
    """Notify staff when a guest taps Call waiter on the QR menu."""
    if table is not None:
        table_label = table.label or str(table.number)
        table_display = str(table)
        floor_name = table.floor.name if table.floor_id else ""
        message = f"{table_display}"
    else:
        table_label = ""
        table_display = ""
        floor_name = ""
        message = ""

    payload = {
        "event": "guest.waiter_call",
        "table_id": table.pk if table else None,
        "table": table_display,
        "table_label": table_label,
        "table_number": table.number if table else None,
        "floor": floor_name,
        "message": message,
        "requested_at": time.time(),
    }

    _group_send(f"waiters.branch.{branch_id}", "waiter.message", payload)
    _group_send(f"waiters.restaurant.{restaurant_id}", "waiter.message", payload)
    if table and table.assigned_to_id:
        _group_send(f"waiter.{table.assigned_to_id}", "waiter.message", payload)
    _cache_waiter_alert(branch_id, payload)
