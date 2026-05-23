from decimal import Decimal

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import DetailView

from apps.common.mixins import RestaurantScopedMixin
from apps.common.permissions import RolePermissionMixin
from apps.menus.models import Menu, MenuCategory, MenuItem
from apps.orders.models import Bill, Order, OrderItem
from apps.orders.services import (
    add_item_to_order,
    close_table_session,
    confirm_order,
    create_order,
    finalize_receipt,
    order_item_quantities,
    order_with_items,
)
from apps.restaurants.models import TableSession


def _order_menu_context(restaurant, order):
    menu = (
        Menu.objects.filter(restaurant=restaurant, is_active=True, is_draft=False)
        .prefetch_related("categories__items")
        .first()
    )
    categories = list(menu.categories.filter(is_active=True).prefetch_related("items")) if menu else []
    quantities = order_item_quantities(order) if order else {}
    for category in categories:
        for item in category.items.all():
            item.order_qty = quantities.get(item.pk, 0)
    return {
        "categories": categories,
        "item_quantities": quantities,
    }


def _order_session_context(session, restaurant, open_order=None):
    """Split session into items already sent to kitchen vs new (open) order."""
    if open_order is not None:
        open_order = order_with_items(open_order)
    else:
        open_order = (
            session.orders.filter(status="open", is_deleted=False)
            .prefetch_related("items__menu_item", "items__modifiers")
            .first()
        )

    sent_items = list(
        OrderItem.objects.filter(
            order__session=session,
            order__is_deleted=False,
            is_deleted=False,
        )
        .exclude(order__status__in=["open", "paid", "cancelled"])
        .select_related("menu_item", "order")
        .order_by("order__created_at", "created_at")
    )
    new_items = list(open_order.active_items) if open_order else []
    all_items = sent_items + new_items

    session_subtotal = sum((i.line_total for i in all_items), Decimal("0"))
    new_subtotal = sum((i.line_total for i in new_items), Decimal("0"))
    sent_subtotal = session_subtotal - new_subtotal

    return {
        "session": session,
        "order": open_order,
        "sent_items": sent_items,
        "new_items": new_items,
        "session_subtotal": session_subtotal,
        "new_subtotal": new_subtotal,
        "sent_subtotal": sent_subtotal,
        "session_item_count": sum(i.quantity for i in all_items),
        "new_item_count": sum(i.quantity for i in new_items),
        **_order_menu_context(restaurant, open_order),
    }


def _render_order_add_response(request, session, order):
    restaurant = session.table.restaurant
    return render(
        request,
        "mobile/partials/order_add_response.html",
        _order_session_context(session, restaurant, open_order=order),
    )


class OrderCreateView(RestaurantScopedMixin, RolePermissionMixin, View):
    template_name = "mobile/order_new.html"
    required_permission = "take_order"

    def get_session(self, session_id):
        return get_object_or_404(
            TableSession,
            pk=session_id,
            table__floor__branch__restaurant=self.get_restaurant(),
            is_active=True,
        )

    def get_or_create_open_order(self, session):
        order = session.orders.filter(status="open", is_deleted=False).first()
        if not order:
            order = create_order(session, self.request.user.employee_profile)
        return order

    def get(self, request, session_id):
        session = self.get_session(session_id)
        order = self.get_or_create_open_order(session)
        return render(
            request,
            self.template_name,
            _order_session_context(session, self.get_restaurant(), open_order=order),
        )

    def post(self, request, session_id):
        session = get_object_or_404(
            TableSession,
            pk=session_id,
            table__floor__branch__restaurant=self.get_restaurant(),
            is_active=True,
        )
        order = self.get_or_create_open_order(session)
        menu_item = get_object_or_404(
            MenuItem,
            pk=request.POST.get("menu_item_id"),
            category__menu__restaurant=self.get_restaurant(),
        )
        add_item_to_order(order, menu_item, quantity=1)
        if request.headers.get("HX-Request"):
            return _render_order_add_response(request, session, order)
        return redirect("order_new", session_id=session_id)


class CloseTableView(RestaurantScopedMixin, RolePermissionMixin, View):
    required_permission = "modify_order"

    def post(self, request, session_id):
        session = get_object_or_404(
            TableSession,
            pk=session_id,
            table__floor__branch__restaurant=self.get_restaurant(),
            is_active=True,
        )
        order = close_table_session(session, request.user, request)
        if order and Bill.objects.filter(order=order).exists():
            messages.success(request, _("Table closed. Print the receipt when ready."))
            return redirect("order_receipt", pk=order.pk)
        messages.success(request, _("Table closed."))
        return redirect("tables")


def _receipt_order_queryset(restaurant):
    return (
        Order.objects.filter(session__table__floor__branch__restaurant=restaurant)
        .select_related("session__table__floor", "waiter__user", "bill")
        .prefetch_related("items__menu_item", "items__modifiers")
    )


class OrderReceiptView(RestaurantScopedMixin, RolePermissionMixin, View):
    """Receipt screen after closing a table (bill requested)."""

    required_permission = "modify_order"
    template_name = "orders/receipt.html"

    def get_order(self, pk):
        order = get_object_or_404(_receipt_order_queryset(self.get_restaurant()), pk=pk)
        if order.status not in ("bill_requested", "paid"):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied(_("No receipt available for this order."))
        return order

    def get(self, request, pk):
        order = self.get_order(pk)
        restaurant = self.get_restaurant()
        company = getattr(restaurant, "legal_profile", None)
        return render(
            request,
            self.template_name,
            {
                "order": order,
                "bill": order.bill,
                "restaurant": restaurant,
                "company": company,
                "receipt_finalized": order.status == "paid",
            },
        )

    def post(self, request, pk):
        order = self.get_order(pk)
        if order.status == "paid":
            return redirect("order_receipt_print", pk=order.pk)
        finalize_receipt(order, request.user, request)
        messages.success(request, _("Receipt printed. Order removed from kitchen."))
        return redirect("order_receipt_print", pk=order.pk)


class OrderReceiptPrintView(RestaurantScopedMixin, RolePermissionMixin, View):
    """Print-friendly receipt (opens browser print dialog)."""

    required_permission = "modify_order"
    template_name = "orders/receipt_print.html"

    def get(self, request, pk):
        order = get_object_or_404(
            _receipt_order_queryset(self.get_restaurant()),
            pk=pk,
            status="paid",
        )
        restaurant = self.get_restaurant()
        company = getattr(restaurant, "legal_profile", None)
        auto_print = request.GET.get("print") != "0"
        return render(
            request,
            self.template_name,
            {
                "order": order,
                "bill": order.bill,
                "restaurant": restaurant,
                "company": company,
                "auto_print": auto_print,
            },
        )


class OrderDetailView(RestaurantScopedMixin, DetailView):
    model = Order
    template_name = "orders/detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return (
            Order.objects.filter(session__table__floor__branch__restaurant=self.get_restaurant())
            .select_related("session__table", "waiter__user")
            .prefetch_related("items__menu_item", "items__modifiers")
        )


class OrderConfirmView(RestaurantScopedMixin, RolePermissionMixin, View):
    required_permission = "take_order"

    def post(self, request, pk):
        order = get_object_or_404(
            Order,
            pk=pk,
            session__table__floor__branch__restaurant=self.get_restaurant(),
        )
        if order.status != "open":
            messages.info(request, _("Order was already sent to the kitchen."))
        elif not order.items.filter(is_deleted=False).exists():
            messages.error(request, _("Add items before sending to the kitchen."))
        else:
            confirm_order(order, request.user, request)
            messages.success(request, _("Order sent to kitchen."))
        if request.headers.get("HX-Request"):
            session = order.session
            return render(
                request,
                "mobile/partials/order_summary.html",
                _order_session_context(session, self.get_restaurant()),
            )
        return redirect("order_new", session_id=order.session_id)


class OrderStatusUpdateView(RestaurantScopedMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(
            Order,
            pk=pk,
            session__table__floor__branch__restaurant=self.get_restaurant(),
        )
        new_status = request.POST.get("status")
        if new_status in dict(Order.STATUS_CHOICES):
            order.status = new_status
            order.save(update_fields=["status", "updated_at"])
        if request.headers.get("HX-Request"):
            return HttpResponse(status=204)
        from django.http import JsonResponse

        return JsonResponse({"status": order.status})
