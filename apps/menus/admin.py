from django.contrib import admin
from modeltranslation.admin import TranslationAdmin, TranslationTabularInline

from .models import Allergen, DietaryTag, Menu, MenuCategory, MenuItem, ModifierGroup, ModifierOption


class MenuCategoryInline(TranslationTabularInline):
    model = MenuCategory
    extra = 0


@admin.register(Menu)
class MenuAdmin(TranslationAdmin):
    list_display = ("name", "restaurant", "is_active", "is_draft")
    inlines = [MenuCategoryInline]


@admin.register(MenuCategory)
class MenuCategoryAdmin(TranslationAdmin):
    list_display = ("name", "menu", "is_active")


@admin.register(MenuItem)
class MenuItemAdmin(TranslationAdmin):
    list_display = ("name", "category", "price", "is_vegetarian", "is_vegan", "is_available", "is_deleted")
    list_filter = ("is_available", "is_vegetarian", "is_vegan", "category__menu", "allergens")
    filter_horizontal = ("allergens",)
    fieldsets = (
        (None, {"fields": ("category", "name", "description", "image", "price", "happy_hour_price")}),
        ("Status", {"fields": ("preparation_time", "sort_order", "is_available", "is_featured")}),
        ("Dietary", {"fields": ("is_vegetarian", "is_vegan", "allergens")}),
        (
            "Nutrition (per serving)",
            {"fields": ("calories", "protein_g", "carbohydrates_g", "fat_g", "fiber_g", "salt_g")},
        ),
    )


@admin.register(Allergen)
class AllergenAdmin(TranslationAdmin):
    list_display = ("name",)


@admin.register(DietaryTag)
class DietaryTagAdmin(admin.ModelAdmin):
    list_display = ("name", "color")
