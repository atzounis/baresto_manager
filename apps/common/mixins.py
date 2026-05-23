from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from apps.accounts.models import EmployeeProfile


def get_employee_profile(user):
    if not user.is_authenticated:
        return None
    try:
        return user.employee_profile
    except EmployeeProfile.DoesNotExist:
        return None


class RestaurantScopedMixin(LoginRequiredMixin):
    """Scope querysets and context to the logged-in staff member's restaurant."""

    def get_restaurant(self):
        profile = get_employee_profile(self.request.user)
        if profile is None:
            raise PermissionDenied("Staff profile required.")
        return profile.restaurant

    def get_branch(self):
        profile = get_employee_profile(self.request.user)
        if profile is None:
            raise PermissionDenied("Staff profile required.")
        if profile.branch_id:
            return profile.branch
        return profile.restaurant.branches.filter(is_active=True).first()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if get_employee_profile(request.user) is None:
            if request.user.is_superuser:
                return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)
            raise PermissionDenied("Staff profile required.")
        return super().dispatch(request, *args, **kwargs)
