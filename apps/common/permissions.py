ROLE_PERMISSIONS = {
    "take_order": {"waiter", "cashier", "manager", "admin"},
    "modify_order": {"waiter", "cashier", "manager", "admin"},
    "apply_discount": {"cashier", "manager", "admin"},
    "close_bill": {"cashier", "manager", "admin"},
    "print_receipt": {"waiter", "cashier", "manager", "admin"},
    "refund": {"manager", "admin"},
    "edit_menu": {"manager", "admin"},
    "edit_company": {"manager", "admin"},
    "view_analytics": {"manager", "admin"},
    "kitchen_display": {"kitchen", "manager", "admin"},
    "manage_users": {"admin"},
}


def role_has_permission(role: str, action: str) -> bool:
    allowed = ROLE_PERMISSIONS.get(action, set())
    return role in allowed


def get_employee_role(user):
    profile = getattr(user, "employee_profile", None)
    if profile:
        return profile.role
    if user.is_superuser:
        return "admin"
    return None


class RolePermissionMixin:
    required_permission = None

    def has_role_permission(self):
        role = get_employee_role(self.request.user)
        if role is None:
            return False
        if self.required_permission is None:
            return True
        return role_has_permission(role, self.required_permission)

    def dispatch(self, request, *args, **kwargs):
        if not self.has_role_permission():
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("Insufficient role permissions.")
        return super().dispatch(request, *args, **kwargs)
