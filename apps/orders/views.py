from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import DetailView, ListView

from apps.common.mixins import RestaurantScopedMixin
from apps.common.permissions import RolePermissionMixin
from apps.menus.models import Menu, MenuCategory, MenuItem
from apps.orders.models import Bill, Order, OrderItem
from apps.realtime import pop_branch_waiter_alerts
from apps.orders.services import (
    add_item_to_order,
    close_table_session,
    confirm_order,
    create_order,
    finalize_receipt,
    order_item_quantities,
    order_with_items,
    update_item_status,
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
    ready_sent_items = [line for line in sent_items if line.status == "ready"]
    served_sent_items = [line for line in sent_items if line.status == "served"]
    kitchen_sent_items = [line for line in sent_items if line.status not in ("ready", "served")]
    new_items = list(open_order.active_items) if open_order else []
    all_items = sent_items + new_items

    session_subtotal = sum((i.line_total for i in all_items), Decimal("0"))
    new_subtotal = sum((i.line_total for i in new_items), Decimal("0"))
    sent_subtotal = session_subtotal - new_subtotal

    return {
        "session": session,
        "order": open_order,
        "sent_items": sent_items,
        "ready_sent_items": ready_sent_items,
        "served_sent_items": served_sent_items,
        "kitchen_sent_items": kitchen_sent_items,
        "ready_item_count": len(ready_sent_items),
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
        if order and Bill.objects.filter(order_id=order.pk).exists():
            return redirect(f"{reverse('tables')}?print_receipt={order.pk}")
        messages.success(request, _("Table closed."))
        return redirect("tables")


def _receipt_order_queryset(restaurant):
    return (
        Order.objects.filter(session__table__floor__branch__restaurant=restaurant)
        .select_related("session__table__floor", "waiter__user", "bill")
        .prefetch_related("items__menu_item", "items__modifiers")
    )


def _receipt_logo_url(request, restaurant, company):
    """Absolute logo URL for print (restaurant logo, else company guest-menu logo)."""
    logo_field = None
    if restaurant.logo:
        logo_field = restaurant.logo
    elif company and company.logo:
        logo_field = company.logo
    if logo_field and logo_field.name:
        return request.build_absolute_uri(logo_field.url)
    return None


def _receipt_context(request, order, restaurant, company, *, receipt_finalized=False):
    from_history = request.GET.get("from") == "history"
    return_url = reverse("order_history") if from_history else reverse("tables")
    return {
        "order": order,
        "bill": order.bill,
        "restaurant": restaurant,
        "company": company,
        "receipt_finalized": receipt_finalized,
        "receipt_logo_url": _receipt_logo_url(request, restaurant, company),
        "return_url": return_url,
        "from_history": from_history,
        "back_label": _("Orders") if from_history else _("Tables"),
    }


def _orders_with_receipts_queryset(branch):
    return (
        Order.objects.filter(
            session__table__floor__branch=branch,
            is_deleted=False,
            status__in=["paid", "bill_requested"],
            bill__isnull=False,
        )
        .select_related("session__table", "waiter__user", "bill")
        .prefetch_related("items__menu_item")
        .order_by("-updated_at")
    )


class OrderHistoryListView(RestaurantScopedMixin, RolePermissionMixin, ListView):
    """Past orders with receipt reprint (waiter, cashier, manager, admin)."""

    required_permission = "print_receipt"
    template_name = "orders/history.html"
    context_object_name = "orders"
    paginate_by = 30

    def get_queryset(self):
        branch = self.get_branch()
        if not branch:
            return Order.objects.none()
        return _orders_with_receipts_queryset(branch)


class OrderReceiptView(RestaurantScopedMixin, RolePermissionMixin, View):
    """Receipt screen after closing a table or from order history."""

    required_permission = "print_receipt"
    template_name = "orders/receipt.html"

    def get_order(self, pk):
        order = get_object_or_404(_receipt_order_queryset(self.get_restaurant()), pk=pk)
        if order.status not in ("bill_requested", "paid"):
            raise PermissionDenied(_("No receipt available for this order."))
        if not hasattr(order, "bill") or order.bill is None:
            raise PermissionDenied(_("No receipt available for this order."))
        return order

    def get(self, request, pk):
        order = self.get_order(pk)
        restaurant = self.get_restaurant()
        company = getattr(restaurant, "legal_profile", None)
        return render(
            request,
            self.template_name,
            _receipt_context(
                request,
                order,
                restaurant,
                company,
                receipt_finalized=order.status == "paid",
            ),
        )

    def post(self, request, pk):
        order = self.get_order(pk)
        if order.status == "paid":
            return redirect("order_receipt_print", pk=order.pk)
        finalize_receipt(order, request.user, request)
        messages.success(request, _("Receipt printed. Order removed from kitchen."))
        return redirect("order_receipt_print", pk=order.pk)


class OrderReceiptQuickPrintView(RestaurantScopedMixin, RolePermissionMixin, View):
    """Finalize bill if needed, then open the print-friendly receipt."""

    required_permission = "print_receipt"

    def _get_order(self, pk):
        order = get_object_or_404(_receipt_order_queryset(self.get_restaurant()), pk=pk)
        if order.status not in ("bill_requested", "paid"):
            raise PermissionDenied(_("No receipt available for this order."))
        if not hasattr(order, "bill") or order.bill is None:
            raise PermissionDenied(_("No receipt available for this order."))
        return order

    def post(self, request, pk):
        order = self._get_order(pk)
        if order.status == "bill_requested":
            finalize_receipt(order, request.user, request)
        return redirect("order_receipt_print", pk=order.pk)


class OrderReceiptPrintView(RestaurantScopedMixin, RolePermissionMixin, View):
    """Print-friendly receipt (opens browser print dialog)."""

    required_permission = "print_receipt"
    template_name = "orders/receipt_print.html"

    def get(self, request, pk):
        order = get_object_or_404(
            _receipt_order_queryset(self.get_restaurant()),
            pk=pk,
            status="paid",
        )
        if not hasattr(order, "bill") or order.bill is None:
            raise PermissionDenied(_("No receipt available for this order."))
        restaurant = self.get_restaurant()
        company = getattr(restaurant, "legal_profile", None)
        auto_print = request.GET.get("print") != "0"
        from_history = request.GET.get("from") == "history"
        return render(
            request,
            self.template_name,
            {
                "order": order,
                "bill": order.bill,
                "restaurant": restaurant,
                "company": company,
                "receipt_logo_url": _receipt_logo_url(request, restaurant, company),
                "auto_print": auto_print,
                "from_history": from_history,
                "return_url": reverse("order_history") if from_history else reverse("tables"),
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


class WaiterItemServedView(RestaurantScopedMixin, RolePermissionMixin, View):
    """Waiter marks a kitchen-ready line item as delivered to the table."""

    required_permission = "take_order"

    def post(self, request, pk):
        item = get_object_or_404(
            OrderItem,
            pk=pk,
            order__session__table__floor__branch__restaurant=self.get_restaurant(),
            is_deleted=False,
            status="ready",
        )
        update_item_status(item, "served", request.user, request)
        session = item.order.session
        if request.headers.get("HX-Request"):
            return render(
                request,
                "mobile/partials/order_summary.html",
                _order_session_context(session, self.get_restaurant()),
            )
        return redirect("order_new", session_id=session.pk)


class WaiterAlertsPollView(RestaurantScopedMixin, RolePermissionMixin, View):
    """HTTP fallback when mobile browsers drop the waiter WebSocket."""

    required_permission = "take_order"

    def get(self, request):
        branch = self.get_branch()
        if not branch:
            return JsonResponse({"alerts": []})
        alerts = pop_branch_waiter_alerts(branch.id)
        return JsonResponse({"alerts": alerts})


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
