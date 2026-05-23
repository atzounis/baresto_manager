from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views import View

from apps.accounts.models import EmployeeProfile


def staff_home_url(user):
    if not user.is_authenticated:
        return "/login/"
    if user.is_superuser and not hasattr(user, "employee_profile"):
        return "/admin/"
    profile = getattr(user, "employee_profile", None)
    if profile is None:
        return "/login/"
    if profile.role == "kitchen":
        return "/kitchen/"
    if profile.role == "waiter":
        return "/tables/"
    return "/dashboard/"


class HomeView(View):
    def get(self, request):
        return redirect(staff_home_url(request.user))


class StaffLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return staff_home_url(self.request.user)


class PinLoginView(View):
    template_name = "accounts/pin_login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(staff_home_url(request.user))
        return render(request, self.template_name)

    def post(self, request):
        pin = request.POST.get("pin", "").strip()
        profile = (
            EmployeeProfile.objects.select_related("user", "restaurant")
            .filter(pin=pin, user__is_active=True)
            .first()
        )
        if profile is None:
            return render(request, self.template_name, {"error": _("Invalid PIN")})
        login(request, profile.user, backend="django.contrib.auth.backends.ModelBackend")
        profile.is_active_shift = True
        profile.save(update_fields=["is_active_shift", "updated_at"])
        return redirect(staff_home_url(profile.user))


class StaffLogoutView(View):
    def post(self, request):
        profile = getattr(request.user, "employee_profile", None)
        if profile:
            profile.is_active_shift = False
            profile.save(update_fields=["is_active_shift", "updated_at"])
        logout(request)
        return redirect("/login/")
