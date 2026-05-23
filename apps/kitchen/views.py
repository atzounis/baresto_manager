from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from apps.common.mixins import RestaurantScopedMixin
from apps.common.permissions import RolePermissionMixin
from apps.orders.models import Order, OrderItem
from apps.orders.services import update_item_status


class KitchenDisplayView(RestaurantScopedMixin, RolePermissionMixin, TemplateView):
    template_name = "kitchen/display.html"
    required_permission = "kitchen_display"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        branch = self.get_branch()
        active_statuses = ["confirmed", "preparing", "partially_ready", "ready"]
        orders = (
            Order.objects.filter(
                session__table__floor__branch=branch,
                status__in=active_statuses,
            )
            .select_related("session__table")
            .prefetch_related(
                Prefetch(
                    "items",
                    queryset=OrderItem.objects.filter(is_deleted=False).select_related("menu_item"),
                )
            )
            .order_by("-is_priority", "created_at")
        )
        ctx["orders"] = orders
        ctx["branch"] = branch
        ctx["stations"] = ["kitchen", "bar", "grill"]
        return ctx


class KitchenItemStatusView(RestaurantScopedMixin, RolePermissionMixin, View):
    required_permission = "kitchen_display"

    def post(self, request, pk):
        item = get_object_or_404(
            OrderItem,
            pk=pk,
            order__session__table__floor__branch__restaurant=self.get_restaurant(),
        )
        status_flow = {"pending": "preparing", "preparing": "ready", "ready": "served"}
        new_status = status_flow.get(item.status, item.status)
        update_item_status(item, new_status, request.user, request)
        return redirect("kitchen")
