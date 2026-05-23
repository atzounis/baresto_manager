from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic import FormView, ListView

from apps.accounts.forms import StaffUserCreateForm, StaffUserUpdateForm
from apps.accounts.models import EmployeeProfile
from apps.common.mixins import RestaurantScopedMixin
from apps.common.permissions import RolePermissionMixin

User = get_user_model()


class StaffUserManageMixin(RestaurantScopedMixin, RolePermissionMixin):
    required_permission = "manage_users"


class StaffUserListView(StaffUserManageMixin, ListView):
    model = EmployeeProfile
    template_name = "accounts/staff_user_list.html"
    context_object_name = "staff_members"
    paginate_by = 50

    def get_queryset(self):
        return (
            EmployeeProfile.objects.filter(restaurant=self.get_restaurant())
            .select_related("user", "branch")
            .order_by("role", "user__username")
        )


class StaffUserCreateView(StaffUserManageMixin, FormView):
    template_name = "accounts/staff_user_form.html"
    form_class = StaffUserCreateForm
    success_url = reverse_lazy("staff_user_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["restaurant"] = self.get_restaurant()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_title"] = _("Add staff member")
        ctx["submit_label"] = _("Create user")
        return ctx

    @transaction.atomic
    def form_valid(self, form):
        restaurant = self.get_restaurant()
        user = User.objects.create_user(
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password"],
            first_name=form.cleaned_data.get("first_name", ""),
            last_name=form.cleaned_data.get("last_name", ""),
            email=form.cleaned_data.get("email", ""),
            is_staff=True,
            is_active=True,
        )
        EmployeeProfile.objects.create(
            user=user,
            restaurant=restaurant,
            branch=form.cleaned_data.get("branch"),
            role=form.cleaned_data["role"],
            pin=form.cleaned_data.get("pin", ""),
        )
        messages.success(self.request, _('User “%(name)s” created.') % {"name": user.username})
        return super().form_valid(form)


class StaffUserUpdateView(StaffUserManageMixin, FormView):
    template_name = "accounts/staff_user_form.html"
    form_class = StaffUserUpdateForm
    success_url = reverse_lazy("staff_user_list")

    def get_profile(self):
        if not hasattr(self, "_profile"):
            self._profile = get_object_or_404(
                EmployeeProfile.objects.select_related("user"),
                pk=self.kwargs["pk"],
                restaurant=self.get_restaurant(),
            )
        return self._profile

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["profile"] = self.get_profile()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = self.get_profile()
        ctx["form_title"] = _("Edit staff member")
        ctx["submit_label"] = _("Save changes")
        ctx["editing_user"] = profile.user
        ctx["is_self"] = profile.user_id == self.request.user.pk
        return ctx

    @transaction.atomic
    def form_valid(self, form):
        profile = self.get_profile()
        user = profile.user
        user.first_name = form.cleaned_data.get("first_name", "")
        user.last_name = form.cleaned_data.get("last_name", "")
        user.email = form.cleaned_data.get("email", "")
        is_active = form.cleaned_data.get("is_active", False)

        if profile.user_id == self.request.user.pk and not is_active:
            form.add_error("is_active", _("You cannot deactivate your own account."))
            return self.form_invalid(form)

        user.is_active = is_active
        user.is_staff = True
        new_password = form.cleaned_data.get("new_password", "")
        if new_password:
            user.set_password(new_password)
        user.save()

        profile.role = form.cleaned_data["role"]
        profile.pin = form.cleaned_data.get("pin", "")
        profile.branch = form.cleaned_data.get("branch")
        profile.save(update_fields=["role", "pin", "branch", "updated_at"])

        messages.success(self.request, _('User “%(name)s” updated.') % {"name": user.username})
        return super().form_valid(form)
