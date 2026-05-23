from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


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


def broadcast_waiter_kitchen_ready(order, *, item_name=None, order_fully_ready=False):
    """Sound/notification alert for waiter when kitchen advances items to ready."""
    staff_ids = _waiter_staff_ids(order)
    if not staff_ids:
        return

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
        for staff_id in staff_ids:
            _group_send(f"waiter.{staff_id}", "waiter.message", payload)

    if order_fully_ready:
        payload = {
            **base,
            "event": "order.ready",
            "message": f"{table_label}",
            "alert": "order_ready",
        }
        for staff_id in staff_ids:
            _group_send(f"waiter.{staff_id}", "waiter.message", payload)


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
