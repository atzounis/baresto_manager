"""Sync modeltranslation fields and remove orphan menu rows without labels."""

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.menus.models import Allergen, Menu, MenuCategory, MenuItem


def _has_any_name(obj) -> bool:
    for attr in ("name_el", "name_en", "name"):
        val = getattr(obj, attr, None)
        if val and str(val).strip():
            return True
    return False


class Command(BaseCommand):
    help = "Sync translation columns and remove empty duplicate categories/items"

    def handle(self, *args, **options):
        synced = 0
        for model in (Menu, MenuCategory, MenuItem, Allergen):
            for obj in model.objects.all():
                changed = False
                if hasattr(obj, "name") and obj.name and not getattr(obj, "name_el", None):
                    obj.name_el = obj.name
                    changed = True
                if hasattr(obj, "name_en") and obj.name and not obj.name_en:
                    obj.name_en = obj.name
                    changed = True
                if hasattr(obj, "name_el") and obj.name_el and obj.name != obj.name_el:
                    obj.name = obj.name_el
                    changed = True
                if hasattr(obj, "description") and obj.description and not getattr(obj, "description_el", None):
                    obj.description_el = obj.description
                    changed = True
                if (
                    hasattr(obj, "description_el")
                    and obj.description_el
                    and getattr(obj, "description", None) != obj.description_el
                ):
                    obj.description = obj.description_el
                    changed = True
                if changed:
                    obj.save()
                    synced += 1

        now = timezone.now()
        empty_q = (
            (Q(name_el__isnull=True) | Q(name_el=""))
            & (Q(name_en__isnull=True) | Q(name_en=""))
            & (Q(name__isnull=True) | Q(name=""))
        )
        empty_categories = MenuCategory.objects.filter(empty_q)
        labeled = MenuCategory.objects.exclude(empty_q).select_related("menu")
        replacement_by_menu_order = {
            (cat.menu_id, cat.sort_order): cat for cat in labeled.order_by("sort_order", "pk")
        }
        replacement_by_restaurant_order = {}
        for cat in labeled:
            replacement_by_restaurant_order[(cat.menu.restaurant_id, cat.sort_order)] = cat

        def find_replacement(category):
            replacement = replacement_by_menu_order.get((category.menu_id, category.sort_order))
            if replacement:
                return replacement
            return replacement_by_restaurant_order.get(
                (category.menu.restaurant_id, category.sort_order)
            )

        moved_items = 0
        removed_items = 0
        empty_menus = Menu.objects.filter(empty_q)
        removed_menus = 0
        for menu in list(empty_menus):
            if not MenuCategory.objects.filter(menu=menu).exists():
                menu.delete()
                removed_menus += 1

        removed_cats = 0
        for cat in list(empty_categories):
            replacement = find_replacement(cat)
            if not replacement:
                continue
            for item in list(MenuItem.all_objects.filter(category=cat)):
                if not _has_any_name(item):
                    item.is_deleted = True
                    item.archived_at = now
                    item.is_available = False
                item.category = replacement
                item.save(
                    update_fields=["category", "is_deleted", "archived_at", "is_available", "updated_at"]
                )
                if item.is_deleted:
                    removed_items += 1
                else:
                    moved_items += 1
            cat.delete()
            removed_cats += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Synced {synced} rows; removed {removed_menus} empty menus, "
                f"{removed_cats} empty categories, moved {moved_items} items, "
                f"soft-deleted {removed_items} unnamed items."
            )
        )
