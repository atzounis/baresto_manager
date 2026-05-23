from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from apps.common.mixins import RestaurantScopedMixin
from apps.common.permissions import RolePermissionMixin
from apps.qr.menu_context import get_guest_menu_context
from apps.qr.services import (
    build_shared_menu_qr_url,
    build_table_qr_url,
    generate_table_qr,
    qr_png_data_uri,
)
from apps.restaurants.models import Restaurant, Table


@method_decorator(xframe_options_sameorigin, name="dispatch")
class GuestMenuView(View):
    template_name = "public/guest_menu.html"

    def get(self, request, table_token):
        table = get_object_or_404(
            Table.objects.select_related("floor__branch__restaurant"),
            qr_token=table_token,
        )
        ctx = get_guest_menu_context(restaurant=table.restaurant, table=table)
        return render(request, self.template_name, ctx)


@method_decorator(xframe_options_sameorigin, name="dispatch")
class GuestMenuSharedView(View):
    """Public menu without a specific table (one QR for all tables)."""

    template_name = "public/guest_menu.html"

    def get(self, request, menu_token):
        restaurant = get_object_or_404(
            Restaurant,
            menu_qr_token=menu_token,
            is_active=True,
        )
        ctx = get_guest_menu_context(restaurant=restaurant, table=None)
        return render(request, self.template_name, ctx)


class MenuEditorMixin(RestaurantScopedMixin, RolePermissionMixin):
    required_permission = "edit_menu"


class GuestMenuHubView(MenuEditorMixin, TemplateView):
    template_name = "menus/guest_menu_hub.html"

    def get_tables(self, branch):
        return (
            Table.objects.filter(floor__branch=branch)
            .select_related("floor")
            .order_by("floor__name", "number")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        branch = self.get_branch()
        restaurant = self.get_restaurant()
        tables = list(self.get_tables(branch)) if branch else []

        for table in tables:
            if not table.qr_code:
                generate_table_qr(table)

        preview_table_id = self.request.GET.get("table")
        preview_table = None
        if preview_table_id:
            preview_table = next((t for t in tables if str(t.pk) == preview_table_id), None)
        if preview_table is None and tables:
            preview_table = tables[0]

        preview_mode = self.request.GET.get("preview", "table")
        if preview_mode not in ("table", "shared"):
            preview_mode = "table"

        if preview_mode == "shared":
            preview_path = reverse(
                "guest_menu_shared",
                kwargs={"menu_token": restaurant.menu_qr_token},
            )
        elif preview_table:
            preview_path = reverse(
                "guest_menu",
                kwargs={"table_token": preview_table.qr_token},
            )
        else:
            preview_path = reverse(
                "guest_menu_shared",
                kwargs={"menu_token": restaurant.menu_qr_token},
            )
            preview_mode = "shared"

        preview_url = self.request.build_absolute_uri(preview_path)

        ctx.update(
            {
                "branch": branch,
                "restaurant": restaurant,
                "tables": tables,
                "preview_table": preview_table,
                "preview_mode": preview_mode,
                "preview_path": preview_path,
                "preview_url": preview_url,
                "shared_menu_url": build_shared_menu_qr_url(restaurant),
                "print_url_shared": reverse("guest_menu_qr_print") + "?mode=shared",
                "print_url_tables": reverse("guest_menu_qr_print") + "?mode=per_table",
            }
        )
        return ctx


class GuestMenuPrintView(MenuEditorMixin, TemplateView):
    template_name = "menus/qr_print.html"

    def get(self, request, *args, **kwargs):
        mode = request.GET.get("mode", "shared")
        if mode not in ("shared", "per_table"):
            mode = "shared"
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        branch = self.get_branch()
        restaurant = self.get_restaurant()
        mode = self.request.GET.get("mode", "shared")
        if mode not in ("shared", "per_table"):
            mode = "shared"

        tables = []
        if branch and mode == "per_table":
            tables = list(
                Table.objects.filter(floor__branch=branch)
                .select_related("floor")
                .order_by("floor__name", "number")
            )
            for table in tables:
                if not table.qr_code:
                    generate_table_qr(table)

        shared_url = build_shared_menu_qr_url(restaurant)
        qr_cards = []
        if mode == "shared":
            qr_cards.append(
                {
                    "title": restaurant.name,
                    "subtitle": _("Scan for digital menu"),
                    "detail": "",
                    "qr_data_uri": qr_png_data_uri(shared_url, box_size=12),
                    "url": shared_url,
                }
            )
        else:
            for table in tables:
                url = build_table_qr_url(table)
                label = table.label or _("Table %(number)s") % {"number": table.number}
                qr_cards.append(
                    {
                        "title": label,
                        "subtitle": restaurant.name,
                        "detail": f"{table.floor.name} · {table.capacity} {_('seats')}",
                        "qr_data_uri": qr_png_data_uri(url, box_size=10),
                        "url": url,
                    }
                )

        ctx.update(
            {
                "restaurant": restaurant,
                "branch": branch,
                "mode": mode,
                "qr_cards": qr_cards,
                "auto_print": self.request.GET.get("print") == "1",
            }
        )
        return ctx
