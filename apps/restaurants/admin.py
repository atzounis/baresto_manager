from django.contrib import admin

from .models import Branch, CompanyLegalProfile, Floor, OpeningHours, Restaurant, Table, TableSession


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")


@admin.register(CompanyLegalProfile)
class CompanyLegalProfileAdmin(admin.ModelAdmin):
    list_display = ("restaurant", "phone", "gemi_number", "show_on_guest_menu")
    search_fields = ("restaurant__name", "trade_name_el", "trade_name_en")


class FloorInline(admin.TabularInline):
    model = Floor
    extra = 0


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant", "is_active")
    inlines = [FloorInline]


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ("number", "label", "floor", "status", "plan_x", "plan_y", "qr_token")
    list_filter = ("status", "floor__branch")
    fieldsets = (
        (None, {"fields": ("floor", "number", "label", "capacity", "status", "assigned_to")}),
        ("Floor plan", {"fields": ("plan_x", "plan_y", "plan_w", "plan_h")}),
        ("QR", {"fields": ("qr_token", "qr_code")}),
    )


@admin.register(TableSession)
class TableSessionAdmin(admin.ModelAdmin):
    list_display = ("table", "cover_count", "is_active", "opened_at")


@admin.register(OpeningHours)
class OpeningHoursAdmin(admin.ModelAdmin):
    list_display = ("branch", "weekday", "opens_at", "closes_at", "is_closed")
