from apps.common.permissions import role_has_permission


def staff_context(request):
    profile = getattr(request.user, "employee_profile", None) if request.user.is_authenticated else None
    role = profile.role if profile else None
    staff_nav = {}
    if role:
        staff_nav = {
            "tables": role_has_permission(role, "take_order"),
            "orders": role_has_permission(role, "print_receipt"),
            "kitchen": role_has_permission(role, "kitchen_display"),
            "menu": role_has_permission(role, "edit_menu"),
            "guest_menu": role_has_permission(role, "edit_menu"),
            "company": role_has_permission(role, "edit_company"),
            "users": role_has_permission(role, "manage_users"),
            "reports": role_has_permission(role, "view_analytics"),
        }
    nav_page_count = sum(1 for show in staff_nav.values() if show)
    return {
        "staff_profile": profile,
        "staff_role": role,
        "staff_nav": staff_nav,
        "staff_nav_multi_page": nav_page_count > 1,
    }
