from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.analytics.utils import log_audit
from apps.orders.models import Bill, Order, OrderItem
from apps.realtime import broadcast_order_event, broadcast_table_update, broadcast_waiter_kitchen_ready


@transaction.atomic
def create_order(session, waiter, notes=""):
    order = Order.objects.create(session=session, waiter=waiter, notes=notes)
    session.table.status = "occupied"
    session.table.save(update_fields=["status"])
    return order


def order_item_quantities(order):
    """Map menu_item_id → total quantity on the order."""
    rows = (
        order.items.filter(is_deleted=False)
        .values("menu_item_id")
        .annotate(total=Sum("quantity"))
    )
    return {row["menu_item_id"]: row["total"] for row in rows}


def order_with_items(order):
    return (
        Order.objects.filter(pk=order.pk)
        .prefetch_related("items__menu_item", "items__modifiers")
        .first()
    )


@transaction.atomic
def add_item_to_order(order, menu_item, quantity=1, modifier_ids=None, station="kitchen", notes=""):
    existing = order.items.filter(menu_item=menu_item, is_deleted=False).first()
    if existing:
        existing.quantity += quantity
        existing.save(update_fields=["quantity", "updated_at"])
        item = existing
    else:
        item = OrderItem.objects.create(
            order=order,
            menu_item=menu_item,
            quantity=quantity,
            unit_price=menu_item.price,
            station=station,
            notes=notes,
        )
        if modifier_ids:
            item.modifiers.set(modifier_ids)
    broadcast_order_event(order, event="order.updated")
    return item


@transaction.atomic
def confirm_order(order, user, request=None):
    order.confirm()
    for item in order.items.filter(status="pending"):
        item.mark_preparing()
    order.status = "preparing"
    order.save(update_fields=["status", "updated_at"])
    log_audit(user, "order.confirm", "orders.Order", order.pk, {}, request)
    broadcast_order_event(order, event="order.confirmed")
    return order


@transaction.atomic
def update_item_status(order_item, new_status, user=None, request=None):
    if new_status == "preparing":
        order_item.mark_preparing()
    elif new_status == "ready":
        order_item.mark_ready()
    elif new_status == "served":
        order_item.status = "served"
        from django.utils import timezone

        order_item.served_at = timezone.now()
        order_item.save(update_fields=["status", "served_at", "updated_at"])

    order = order_item.order
    items = list(order.items.filter(is_deleted=False))
    if items and all(i.status == "served" for i in items):
        order.status = "served"
    elif items and all(i.status in ("ready", "served") for i in items):
        order.status = "ready"
    elif any(i.status == "ready" for i in items):
        order.status = "partially_ready"
    elif any(i.status == "preparing" for i in items):
        order.status = "preparing"
    order.save(update_fields=["status", "updated_at"])

    if user:
        log_audit(user, "order_item.status", "orders.OrderItem", order_item.pk, {"status": new_status}, request)

    broadcast_order_event(
        order,
        event="order_item.updated",
        extra={
            "item_id": order_item.pk,
            "status": new_status,
            "item_name": order_item.menu_item.name,
        },
    )

    if new_status == "ready":
        item_name = order_item.menu_item.name
        broadcast_waiter_kitchen_ready(
            order,
            item_name=item_name,
            order_fully_ready=(order.status == "ready"),
        )

    return order_item


@transaction.atomic
def create_bill(order, tax_rate=Decimal("0.10"), discount=Decimal("0")):
    subtotal = order.subtotal
    tax = (subtotal * tax_rate).quantize(Decimal("0.01"))
    total = subtotal + tax - discount
    bill, _ = Bill.objects.update_or_create(
        order=order,
        defaults={
            "subtotal": subtotal,
            "tax": tax,
            "discount": discount,
            "total": total,
        },
    )
    order.status = "bill_requested"
    order.save(update_fields=["status", "updated_at"])
    broadcast_order_event(order, event="order.bill_requested")
    return bill


@transaction.atomic
def close_table_session(session, user, request=None):
    """
    Send the active order to the kitchen (if needed), issue the bill, and free the table.
    """
    table = session.table
    order = (
        session.orders.filter(is_deleted=False)
        .exclude(status__in=["paid", "cancelled"])
        .order_by("-created_at")
        .first()
    )

    if order and order.items.filter(is_deleted=False).exists():
        if order.status == "open":
            confirm_order(order, user, request)
        elif order.status == "confirmed":
            for item in order.items.filter(is_deleted=False, status="pending"):
                item.mark_preparing()
            order.status = "preparing"
            order.save(update_fields=["status", "updated_at"])
            broadcast_order_event(order, event="order.confirmed")
        create_bill(order)

    session.is_active = False
    session.closed_at = timezone.now()
    session.save(update_fields=["is_active", "closed_at", "updated_at"])

    table.status = "free"
    table.save(update_fields=["status"])
    broadcast_table_update(table)

    if order:
        log_audit(user, "table.close", "restaurants.TableSession", session.pk, {"order_id": order.pk}, request)

    return order


@transaction.atomic
def finalize_receipt(order, user, request=None):
    """Mark bill paid, clear kitchen ticket, and record receipt print."""
    now = timezone.now()
    for item in order.items.filter(is_deleted=False):
        if item.status != "served":
            item.status = "served"
            item.served_at = item.served_at or now
            item.save(update_fields=["status", "served_at", "updated_at"])

    order.status = "paid"
    order.closed_at = order.closed_at or now
    order.save(update_fields=["status", "closed_at", "updated_at"])

    bill = getattr(order, "bill", None)
    if bill:
        bill.is_paid = True
        bill.paid_at = now
        bill.receipt_printed = True
        bill.save(update_fields=["is_paid", "paid_at", "receipt_printed", "updated_at"])

    log_audit(user, "receipt.print", "orders.Order", order.pk, {}, request)
    broadcast_order_event(order, event="order.closed")
    return order


@transaction.atomic
def clear_kitchen_ticket(order, user=None, request=None):
    """
    Remove a stuck ticket from the kitchen display: ensure bill exists, mark paid/served.
    """
    if order.status in ("paid", "cancelled"):
        return order
    if not Bill.objects.filter(order=order).exists():
        if order.items.filter(is_deleted=False).exists():
            create_bill(order)
        else:
            order.status = "cancelled"
            order.closed_at = timezone.now()
            order.save(update_fields=["status", "closed_at", "updated_at"])
            broadcast_order_event(order, event="order.closed")
            return order
    finalize_receipt(order, user, request)
    return order
