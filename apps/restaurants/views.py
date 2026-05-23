import json

from django.contrib import messages
from django.db.models import Count, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView

from apps.common.mixins import RestaurantScopedMixin
from apps.common.permissions import RolePermissionMixin, get_employee_role, role_has_permission
from apps.realtime import broadcast_table_update
from apps.restaurants.forms import CompanyLegalProfileForm, FloorForm, TableForm
from apps.restaurants.models import CompanyLegalProfile, Floor, Table, TableSession


def _tables_queryset(branch):
    return (
        Table.objects.filter(floor__branch=branch)
        .select_related("floor", "assigned_to__user")
        .prefetch_related(
            Prefetch("sessions", queryset=TableSession.objects.filter(is_active=True)),
        )
        .order_by("floor_id", "number")
    )


def _parse_floor_id(value):
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_floor_filter(request, floors_qs):
    floor_pk = _parse_floor_id(request.GET.get("floor"))
    if floor_pk and floors_qs.filter(pk=floor_pk).exists():
        return floor_pk
    return None


def _build_tables_url(request, floor_pk=None, view_mode=None):
    """Build tables page URL preserving manage params and optional floor filter."""
    q = request.GET.copy()
    if floor_pk:
        q["floor"] = str(floor_pk)
    else:
        q.pop("floor", None)
    if view_mode is not None:
        q["view"] = view_mode
    base = reverse("tables")
    return f"{base}?{q.urlencode()}" if q else base


def _table_to_plan_dict(table, index=0):
    cols = 4
    default_x = (index % cols) * 22 + 4
    default_y = (index // cols) * 22 + 8
    session = table.sessions.all()[0] if table.sessions.all() else None
    return {
        "id": table.pk,
        "label": table.label or f"T{table.number}",
        "number": table.number,
        "floor": table.floor.name,
        "floor_id": table.floor_id,
        "status": table.status,
        "status_display": str(table.get_status_display()),
        "capacity": table.capacity,
        "x": table.plan_x if table.plan_x is not None else default_x,
        "y": table.plan_y if table.plan_y is not None else default_y,
        "w": table.plan_w,
        "h": table.plan_h,
        "has_position": table.plan_x is not None and table.plan_y is not None,
        "session_id": session.pk if session else None,
        "open_url": f"/orders/new/{session.pk}/" if session else None,
        "open_post_url": f"/tables/{table.pk}/open/",
    }


class TableFloorView(RestaurantScopedMixin, RolePermissionMixin, TemplateView):
    template_name = "restaurants/tables.html"
    required_permission = "take_order"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        branch = self.get_branch()
        floors = (
            Floor.objects.filter(branch=branch)
            .annotate(table_count=Count("tables"))
            .order_by("name")
        )
        filter_floor_id = _resolve_floor_filter(self.request, floors) if branch else None

        all_tables = list(_tables_queryset(branch)) if branch else []
        if filter_floor_id:
            tables = [t for t in all_tables if t.floor_id == filter_floor_id]
        else:
            tables = all_tables

        view_mode = self.request.GET.get("view", "list")
        if view_mode not in ("list", "plan"):
            view_mode = "list"

        role = get_employee_role(self.request.user)
        can_edit_plan = role_has_permission(role, "edit_menu")

        ctx["branch"] = branch
        ctx["floors"] = floors
        ctx["filter_floor_id"] = filter_floor_id
        ctx["floor_filter_all_url"] = _build_tables_url(
            self.request, floor_pk=None, view_mode=view_mode
        )
        ctx["floor_filter_items"] = [
            {
                "id": f.id,
                "name": f.name,
                "table_count": f.table_count,
                "url": _build_tables_url(self.request, floor_pk=f.id, view_mode=view_mode),
            }
            for f in floors
        ]
        ctx["tables_list_url"] = _build_tables_url(
            self.request, floor_pk=filter_floor_id, view_mode="list"
        )
        ctx["tables_plan_url"] = _build_tables_url(
            self.request, floor_pk=filter_floor_id, view_mode="plan"
        )
        ctx["tables"] = tables
        ctx["view_mode"] = view_mode
        ctx["can_edit_plan"] = can_edit_plan
        ctx["can_manage_tables"] = can_edit_plan
        table_form = None
        if can_edit_plan and branch:
            initial = {}
            if filter_floor_id:
                initial["floor"] = filter_floor_id
            table_form = TableForm(branch=branch, initial=initial or None)
        ctx["table_form"] = table_form
        ctx["open_manage"] = self.request.GET.get("manage") == "1"
        ctx["tables_url"] = self.request.get_full_path()
        ctx["tables_json"] = json.dumps(
            [_table_to_plan_dict(t, i) for i, t in enumerate(all_tables)]
        )
        ctx["floors_json"] = json.dumps([{"id": f.id, "name": f.name} for f in floors])
        floors_select = [
            {
                "id": f.id,
                "name": f.name,
                "label": f.name,
                "table_count": f.table_count,
            }
            for f in floors
        ]
        ctx["floors_select_json"] = json.dumps(floors_select)
        ctx["floor_field_config"] = None
        if table_form and branch:
            from django.middleware.csrf import get_token

            selected_floor = ""
            if initial.get("floor"):
                selected_floor = str(initial["floor"])
            ctx["floor_field_config"] = {
                "floors": floors_select,
                "selectedId": selected_floor,
                "csrfToken": get_token(self.request),
                "floorApiUrl": reverse("floor_api"),
                "i18n": {
                    "addFloor": _("Add floor"),
                    "newFloorTitle": _("New floor"),
                    "save": _("Save"),
                    "cancel": _("Cancel"),
                    "saveFailed": _("Save failed"),
                    "newFloorPlaceholder": _("e.g. Terrace, 1st floor"),
                },
            }
        ctx["default_floor_id"] = filter_floor_id or (floors[0].id if floors else None)
        return ctx


class TableManageMixin(RestaurantScopedMixin, RolePermissionMixin):
    required_permission = "edit_menu"


def _next_table_number(floor):
    last = (
        Table.objects.filter(floor=floor)
        .order_by("-number")
        .values_list("number", flat=True)
        .first()
    )
    return (last or 0) + 1


def _default_plan_position(floor):
    count = Table.objects.filter(floor=floor).count()
    return {
        "plan_x": (count % 4) * 22 + 4,
        "plan_y": (count // 4) * 22 + 8,
    }


def _floor_json(floor):
    table_count = getattr(floor, "table_count", None)
    if table_count is None:
        table_count = floor.tables.count()
    return {
        "id": floor.pk,
        "name": floor.name,
        "label": floor.name,
        "table_count": table_count,
    }


def _parse_json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body)
    except json.JSONDecodeError:
        return None


class FloorAPIView(TableManageMixin, View):
    """List and create floors (JSON) for the current branch."""

    def get(self, request):
        branch = self.get_branch()
        if branch is None:
            return JsonResponse({"floors": []})
        floors = Floor.objects.filter(branch=branch).annotate(table_count=Count("tables")).order_by("name")
        return JsonResponse({"floors": [_floor_json(f) for f in floors]})

    def post(self, request):
        branch = self.get_branch()
        if branch is None:
            return JsonResponse({"detail": _("No branch configured.")}, status=400)

        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"detail": _("Invalid JSON.")}, status=400)

        form = FloorForm({"name": payload.get("name", "")})
        if not form.is_valid():
            return JsonResponse({"detail": _("Enter a floor name.")}, status=400)

        name = form.cleaned_data["name"].strip()
        floor = Floor.objects.filter(branch=branch, name__iexact=name).first()
        created = False
        if not floor:
            floor = Floor.objects.create(branch=branch, name=name)
            created = True
        floor.table_count = floor.tables.count()
        return JsonResponse({"floor": _floor_json(floor), "created": created}, status=201 if created else 200)


class FloorDetailAPIView(TableManageMixin, View):
    def get_floor(self, request, pk):
        branch = self.get_branch()
        return get_object_or_404(Floor, pk=pk, branch=branch)

    def patch(self, request, pk):
        floor = self.get_floor(request, pk)
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"detail": _("Invalid JSON.")}, status=400)

        form = FloorForm({"name": payload.get("name", "")}, instance=floor)
        if not form.is_valid():
            return JsonResponse({"detail": _("Enter a floor name.")}, status=400)

        name = form.cleaned_data["name"].strip()
        if Floor.objects.filter(branch=floor.branch, name__iexact=name).exclude(pk=floor.pk).exists():
            return JsonResponse({"detail": _("A floor with this name already exists.")}, status=400)

        floor.name = name
        floor.save(update_fields=["name"])
        floor.table_count = floor.tables.count()
        return JsonResponse({"floor": _floor_json(floor)})

    def delete(self, request, pk):
        floor = self.get_floor(request, pk)
        table_count = floor.tables.count()
        if table_count:
            return JsonResponse(
                {
                    "detail": _(
                        "Cannot delete “%(name)s” — it has %(count)s table(s). Move or delete them first."
                    )
                    % {"name": floor.name, "count": table_count},
                },
                status=400,
            )
        name = floor.name
        floor.delete()
        return JsonResponse({"deleted": True, "id": pk, "name": name})


class TableCreateView(TableManageMixin, View):
    def post(self, request):
        branch = self.get_branch()
        form = TableForm(data=request.POST, branch=branch)
        if not form.is_valid():
            messages.error(request, _("Could not add table. Check the form and try again."))
            return redirect(request.POST.get("next", reverse("tables")))

        table = form.save(commit=False)
        if not table.number:
            table.number = _next_table_number(table.floor)
        if not table.label:
            table.label = f"T{table.number}"
        pos = _default_plan_position(table.floor)
        table.plan_x = pos["plan_x"]
        table.plan_y = pos["plan_y"]
        table.save()
        messages.success(
            request,
            _('Table “%(label)s” added with %(seats)s seats.') % {"label": table.label, "seats": table.capacity},
        )
        return redirect(request.POST.get("next", reverse("tables")))


class TableUpdateView(TableManageMixin, View):
    def post(self, request, pk):
        table = get_object_or_404(
            Table,
            pk=pk,
            floor__branch__restaurant=self.get_restaurant(),
        )
        capacity = request.POST.get("capacity")
        label = request.POST.get("label", "").strip()
        try:
            capacity = int(capacity)
            if capacity < 1 or capacity > 99:
                raise ValueError
        except (TypeError, ValueError):
            messages.error(request, _("Seats must be a number between 1 and 99."))
            return redirect(request.POST.get("next", reverse("tables")))

        table.capacity = capacity
        if label:
            table.label = label
        table.save(update_fields=["capacity", "label"])
        broadcast_table_update(table)
        messages.success(request, _("Table updated."))
        return redirect(request.POST.get("next", reverse("tables")))


class TableDeleteView(TableManageMixin, View):
    def post(self, request, pk):
        table = get_object_or_404(
            Table,
            pk=pk,
            floor__branch__restaurant=self.get_restaurant(),
        )
        label = table.label or str(table.number)
        if TableSession.objects.filter(table=table, is_active=True).exists():
            messages.error(
                request,
                _('Cannot delete “%(label)s” while it has an active session.') % {"label": label},
            )
            return redirect(request.POST.get("next", reverse("tables")))

        if table.status == "occupied":
            messages.error(
                request,
                _('Cannot delete “%(label)s” while it is occupied. Close the session first.') % {"label": label},
            )
            return redirect(request.POST.get("next", reverse("tables")))

        table.delete()
        messages.success(request, _('Table “%(label)s” removed.') % {"label": label})
        return redirect(request.POST.get("next", reverse("tables")))


class FloorPlanSaveView(RestaurantScopedMixin, View):
    """Persist table positions from the floor plan editor."""

    def post(self, request):
        if not role_has_permission(get_employee_role(request.user), "edit_menu"):
            return JsonResponse({"detail": "Forbidden"}, status=403)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"detail": "Invalid JSON"}, status=400)

        positions = payload.get("tables", [])
        branch = self.get_branch()
        updated = 0

        for item in positions:
            table_id = item.get("id")
            if table_id is None:
                continue
            table = get_object_or_404(
                Table,
                pk=table_id,
                floor__branch=branch,
                floor__branch__restaurant=self.get_restaurant(),
            )
            table.plan_x = max(0, min(100 - float(item.get("w", table.plan_w)), float(item["x"])))
            table.plan_y = max(0, min(100 - float(item.get("h", table.plan_h)), float(item["y"])))
            table.plan_w = max(6, min(40, float(item.get("w", table.plan_w))))
            table.plan_h = max(6, min(40, float(item.get("h", table.plan_h))))
            table.save(update_fields=["plan_x", "plan_y", "plan_w", "plan_h"])
            updated += 1

        return JsonResponse({"ok": True, "updated": updated})


class AssignWaiterView(RestaurantScopedMixin, View):
    def post(self, request, pk):
        table = get_object_or_404(
            Table,
            pk=pk,
            floor__branch__restaurant=self.get_restaurant(),
        )
        profile = request.user.employee_profile
        if request.POST.get("clear"):
            table.assigned_to = None
        else:
            table.assigned_to = profile
        table.save(update_fields=["assigned_to"])
        broadcast_table_update(table)
        return redirect("tables")


class OpenSessionView(RestaurantScopedMixin, View):
    def post(self, request, table_id):
        table = get_object_or_404(
            Table,
            pk=table_id,
            floor__branch__restaurant=self.get_restaurant(),
        )
        cover_count = int(request.POST.get("cover_count", 2))
        TableSession.objects.filter(table=table, is_active=True).update(is_active=False)
        session = TableSession.objects.create(table=table, cover_count=cover_count)
        table.status = "occupied"
        table.save(update_fields=["status"])
        broadcast_table_update(table)
        return redirect("order_new", session_id=session.pk)


class CompanyDetailsView(RestaurantScopedMixin, RolePermissionMixin, View):
    """Edit mandatory GR/EN catalogue legal disclosures for the restaurant."""

    required_permission = "edit_company"
    template_name = "restaurants/company_details.html"

    def get_profile(self, restaurant):
        profile, created = CompanyLegalProfile.objects.get_or_create(restaurant=restaurant)
        if created:
            profile.sync_from_branch()
            profile.save()
        return profile

    def get(self, request):
        restaurant = self.get_restaurant()
        profile = self.get_profile(restaurant)
        branch = restaurant.branches.filter(is_active=True).first()
        return render(
            request,
            self.template_name,
            {
                "form": CompanyLegalProfileForm(instance=profile),
                "profile": profile,
                "restaurant": restaurant,
                "branch": branch,
            },
        )

    def post(self, request):
        restaurant = self.get_restaurant()
        profile = self.get_profile(restaurant)
        form = CompanyLegalProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, _("Company details saved."))
            return redirect("company_details")
        branch = restaurant.branches.filter(is_active=True).first()
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "profile": profile,
                "restaurant": restaurant,
                "branch": branch,
            },
        )
