from django.contrib import messages
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.common.mixins import RestaurantScopedMixin
from apps.common.permissions import RolePermissionMixin, get_employee_role, role_has_permission
from apps.menus.forms import MenuCategoryForm, MenuItemForm
from apps.menus.i18n import localized_name
from apps.menus.models import Menu, MenuCategory, MenuItem


class MenuEditorMixin(RestaurantScopedMixin, RolePermissionMixin):
    required_permission = "edit_menu"


class MenuManageView(MenuEditorMixin, ListView):
    template_name = "menus/manage.html"
    context_object_name = "menus"

    def get_queryset(self):
        categories = (
            MenuCategory.objects.annotate(
                product_count=Count("items", filter=Q(items__is_deleted=False)),
            )
            .prefetch_related("items__allergens")
            .order_by("sort_order", "name_el", "name_en")
        )
        return (
            Menu.objects.filter(restaurant=self.get_restaurant())
            .prefetch_related(Prefetch("categories", queryset=categories))
            .order_by("name")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_edit"] = True
        return ctx


class MenuItemCreateView(MenuEditorMixin, CreateView):
    model = MenuItem
    form_class = MenuItemForm
    template_name = "menus/item_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["restaurant"] = self.get_restaurant()
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        category_id = self.request.GET.get("category")
        if category_id:
            initial["category"] = category_id
        return initial

    def form_valid(self, form):
        messages.success(self.request, f"Added {form.instance.name}.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("menu_manage")


class MenuItemUpdateView(MenuEditorMixin, UpdateView):
    model = MenuItem
    form_class = MenuItemForm
    template_name = "menus/item_form.html"
    context_object_name = "item"

    def get_queryset(self):
        return MenuItem.objects.filter(category__menu__restaurant=self.get_restaurant()).prefetch_related(
            "allergens"
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["restaurant"] = self.get_restaurant()
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, f"Saved {form.instance.name}.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("menu_manage")


class MenuItemDeleteView(MenuEditorMixin, View):
    def post(self, request, pk):
        item = get_object_or_404(
            MenuItem,
            pk=pk,
            category__menu__restaurant=self.get_restaurant(),
        )
        item.is_deleted = True
        item.archived_at = timezone.now()
        item.is_available = False
        item.save(update_fields=["is_deleted", "archived_at", "is_available", "updated_at"])
        messages.success(request, f"Removed {item.name}.")
        return redirect("menu_manage")


class MenuCategoryCreateView(MenuEditorMixin, CreateView):
    model = MenuCategory
    form_class = MenuCategoryForm
    template_name = "menus/category_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["restaurant"] = self.get_restaurant()
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        menus = Menu.objects.filter(restaurant=self.get_restaurant(), is_active=True)
        menu_id = self.request.GET.get("menu")
        if menu_id and menus.filter(pk=menu_id).exists():
            initial["menu"] = menu_id
            return initial
        if menus.count() == 1:
            initial["menu"] = menus.first().pk
        return initial

    def form_valid(self, form):
        messages.success(self.request, f"Added category {form.instance.name}.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("menu_manage")


class MenuCategoryDeleteView(MenuEditorMixin, View):
    def post(self, request, pk):
        category = get_object_or_404(
            MenuCategory,
            pk=pk,
            menu__restaurant=self.get_restaurant(),
        )
        label = localized_name(category) or str(category.pk)
        if MenuItem.objects.filter(category=category).exists():
            messages.error(
                request,
                _('Cannot delete category “%(name)s” because it still has products.') % {"name": label},
            )
            return redirect("menu_manage")

        category.delete()
        messages.success(request, _('Category “%(name)s” removed.') % {"name": label})
        return redirect("menu_manage")


class MenuItemToggleView(RestaurantScopedMixin, View):
    def post(self, request, pk):
        if not role_has_permission(get_employee_role(request.user), "edit_menu"):
            return HttpResponseForbidden()
        item = get_object_or_404(MenuItem, pk=pk, category__menu__restaurant=self.get_restaurant())
        item.is_available = not item.is_available
        item.save(update_fields=["is_available", "updated_at"])
        from django.shortcuts import render

        return render(request, "menus/partials/item_row.html", {"item": item})
