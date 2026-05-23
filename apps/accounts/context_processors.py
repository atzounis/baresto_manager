def staff_context(request):
    profile = getattr(request.user, "employee_profile", None) if request.user.is_authenticated else None
    return {
        "staff_profile": profile,
        "staff_role": profile.role if profile else None,
    }
