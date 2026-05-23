from django.contrib import admin

from .models import Bill, Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "status", "waiter", "created_at")
    list_filter = ("status",)
    inlines = [OrderItemInline]


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ("order", "total", "is_paid", "payment_method")
