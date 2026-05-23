from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import DetailView

from apps.common.mixins import RestaurantScopedMixin
from apps.common.permissions import RolePermissionMixin
from apps.menus.models import Menu, MenuCategory, MenuItem
from apps.orders.models import Order
from apps.orders.services import (
    add_item_to_order,
    close_table_session,
    confirm_order,
    create_order,
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


def _render_order_add_response(request, session, order):
    order = order_with_items(order)
    restaurant = order.session.table.restaurant
    menu_ctx = _order_menu_context(restaurant, order)
    return render(
        request,
        "mobile/partials/order_add_response.html",
        {
            "session": session,
            "order": order,
            **menu_ctx,
        },
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
        order = order_with_items(self.get_or_create_open_order(session))
        menu_ctx = _order_menu_context(self.get_restaurant(), order)
        return render(
            request,
            self.template_name,
            {"session": session, "order": order, **menu_ctx},
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
        messages.success(
            request,
            _("Table closed. Order sent to kitchen and bill requested.")
            if order
            else _("Table closed."),
        )
        return redirect("tables")


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
            order = order_with_items(order)
            menu_ctx = _order_menu_context(self.get_restaurant(), order)
            return render(
                request,
                "mobile/partials/order_summary.html",
                {"session": session, "order": order, **menu_ctx},
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
