from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views import View
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from apps.common.mixins import RestaurantScopedMixin
from apps.common.permissions import RolePermissionMixin
from apps.menus.i18n import localized_name
from apps.qr.menu_context import get_guest_menu_context
from apps.qr.services import (
    build_shared_menu_qr_url,
    build_table_qr_url,
    generate_table_qr,
    qr_png_data_uri,
)
from apps.realtime import broadcast_guest_waiter_call
from apps.restaurants.models import CompanyLegalProfile, Restaurant, Table

GUEST_CALL_WAITER_COOLDOWN_SECONDS = 30


def _restaurant_brand_name(restaurant):
    """Trade name from /company/, localized for the active UI language."""
    try:
        profile = restaurant.legal_profile
    except CompanyLegalProfile.DoesNotExist:
        return restaurant.name
    return localized_name(profile, base="trade_name") or restaurant.name


def _guest_call_throttle_key(request, scope_key):
    ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
    if not ip:
        ip = request.META.get("REMOTE_ADDR", "unknown")
    return f"guest_call_waiter:{scope_key}:{ip}"


def _guest_call_waiter_allowed(request, scope_key):
    key = _guest_call_throttle_key(request, scope_key)
    if cache.get(key):
        return False
    cache.set(key, 1, timeout=GUEST_CALL_WAITER_COOLDOWN_SECONDS)
    return True


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(require_POST, name="dispatch")
class GuestCallWaiterTableView(View):
    """Public endpoint: guest at a table requests staff assistance."""

    def post(self, request, table_token):
        table = get_object_or_404(
            Table.objects.select_related("floor__branch", "floor__branch__restaurant"),
            qr_token=table_token,
        )
        scope = str(table_token)
        if not _guest_call_waiter_allowed(request, scope):
            return JsonResponse(
                {"ok": False, "error": _("Please wait before calling again.")},
                status=429,
            )
        branch = table.branch
        broadcast_guest_waiter_call(
            branch_id=branch.id,
            restaurant_id=branch.restaurant_id,
            table=table,
        )
        return JsonResponse({"ok": True})


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(require_POST, name="dispatch")
class GuestCallWaiterSharedView(View):
    """Public endpoint: guest on shared menu QR (no table) requests staff."""

    def post(self, request, menu_token):
        restaurant = get_object_or_404(
            Restaurant,
            menu_qr_token=menu_token,
            is_active=True,
        )
        branch = restaurant.branches.filter(is_active=True).first()
        if not branch:
            return JsonResponse({"ok": False, "error": _("Restaurant unavailable.")}, status=503)
        scope = f"shared:{menu_token}"
        if not _guest_call_waiter_allowed(request, scope):
            return JsonResponse(
                {"ok": False, "error": _("Please wait before calling again.")},
                status=429,
            )
        broadcast_guest_waiter_call(
            branch_id=branch.id,
            restaurant_id=restaurant.id,
            table=None,
        )
        return JsonResponse({"ok": True})


@method_decorator(xframe_options_sameorigin, name="dispatch")
class GuestMenuView(View):
    template_name = "public/guest_menu.html"

    def get(self, request, table_token):
        table = get_object_or_404(
            Table.objects.select_related("floor__branch__restaurant"),
            qr_token=table_token,
        )
        ctx = get_guest_menu_context(restaurant=table.restaurant, table=table)
        ctx["call_waiter_url"] = reverse(
            "guest_call_waiter",
            kwargs={"table_token": table.qr_token},
        )
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
        ctx["call_waiter_url"] = reverse(
            "guest_call_waiter_shared",
            kwargs={"menu_token": restaurant.menu_qr_token},
        )
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

        preview_url = f"{settings.SITE_BASE_URL.rstrip('/')}{preview_path}"

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

        brand_name = _restaurant_brand_name(restaurant)

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
                    "title": brand_name,
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
                        "subtitle": brand_name,
                        "detail": f"{table.floor.name} · {table.capacity} {_('seats')}",
                        "qr_data_uri": qr_png_data_uri(url, box_size=10),
                        "url": url,
                    }
                )

        ctx.update(
            {
                "restaurant": restaurant,
                "brand_name": brand_name,
                "branch": branch,
                "mode": mode,
                "qr_cards": qr_cards,
                "auto_print": self.request.GET.get("print") == "1",
            }
        )
        return ctx
