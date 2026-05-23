from django.contrib import admin

from .models import EmployeeProfile


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "restaurant", "role", "is_active_shift")
    list_filter = ("role", "restaurant")
