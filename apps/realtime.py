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
