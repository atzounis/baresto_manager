from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone
from django.views.generic import TemplateView

from apps.common.mixins import RestaurantScopedMixin
from apps.common.permissions import RolePermissionMixin
from apps.orders.models import Bill, Order, OrderItem
from apps.restaurants.models import Table, TableSession


class DashboardView(RestaurantScopedMixin, TemplateView):
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        restaurant = self.get_restaurant()
        branch = self.get_branch()
        today = timezone.now().date()

        tables = Table.objects.filter(floor__branch=branch)
        ctx["tables"] = tables
        ctx["table_counts"] = tables.values("status").annotate(count=Count("id"))

        active_orders = Order.objects.filter(
            session__table__floor__branch=branch,
            status__in=["open", "confirmed", "preparing", "partially_ready", "ready"],
        ).select_related("session__table")
        ctx["active_orders"] = active_orders[:20]

        revenue = (
            Bill.objects.filter(
                order__session__table__floor__branch=branch,
                is_paid=True,
                paid_at__date=today,
            ).aggregate(total=Sum("total"))["total"]
            or Decimal("0")
        )
        ctx["revenue_today"] = revenue
        ctx["branch"] = branch
        ctx["restaurant"] = restaurant
        return ctx


class ReportsView(RestaurantScopedMixin, RolePermissionMixin, TemplateView):
    template_name = "reports.html"
    required_permission = "view_analytics"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        restaurant = self.get_restaurant()
        since = timezone.now() - timedelta(days=7)
        top_items = (
            OrderItem.objects.filter(
                order__session__table__floor__branch__restaurant=restaurant,
                created_at__gte=since,
                is_deleted=False,
            )
            .values("menu_item__name")
            .annotate(qty=Sum("quantity"))
            .order_by("-qty")[:10]
        )
        ctx["top_items"] = top_items
        ctx["sessions_week"] = TableSession.objects.filter(
            table__floor__branch__restaurant=restaurant,
            opened_at__gte=since,
        ).count()
        return ctx
