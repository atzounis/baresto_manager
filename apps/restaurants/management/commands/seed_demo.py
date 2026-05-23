from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.models import EmployeeProfile
from apps.menus.models import Allergen, Menu, MenuCategory, MenuItem
from apps.restaurants.models import Branch, CompanyLegalProfile, Floor, Restaurant, Table

User = get_user_model()


def _set_translated_name(obj, name_el, name_en):
    obj.name_el = name_el
    obj.name_en = name_en
    obj.name = name_el
    obj.save(update_fields=["name", "name_el", "name_en"])


def _set_translated_text(obj, el, en, *, field="description"):
    setattr(obj, f"{field}_el", el)
    setattr(obj, f"{field}_en", en)
    setattr(obj, field, el)
    obj.save(update_fields=[field, f"{field}_el", f"{field}_en"])


class Command(BaseCommand):
    help = "Seed demo restaurant, menu, tables, and staff"

    def handle(self, *args, **options):
        restaurant, _ = Restaurant.objects.get_or_create(
            name="Baresto Demo",
            defaults={
                "primary_color": "#2DB5A3",
                "is_active": True,
                "default_language": "el",
                "supported_languages": "el,en",
            },
        )
        branch, _ = Branch.objects.get_or_create(
            restaurant=restaurant,
            name="Main Street",
            defaults={
                "address": "1 Οδός Ερμού, 105 63 Αθήνα",
                "phone": "+30 210 000 0000",
                "timezone": "Europe/Athens",
            },
        )
        profile, _ = CompanyLegalProfile.objects.get_or_create(restaurant=restaurant)
        profile.trade_name_el = "Baresto Demo ΕΠΕ"
        profile.trade_name_en = "Baresto Demo Ltd"
        profile.address_el = branch.address
        profile.address_en = "1 Ermou Street, 105 63 Athens, Greece"
        profile.phone = branch.phone
        profile.gemi_number = "123456789000"
        profile.save()
        floor, _ = Floor.objects.get_or_create(branch=branch, name="Ground Floor")

        staff_defs = [
            ("admin", "admin", "admin1234", "0000", "admin"),
            ("manager", "manager", "manager1234", "1111", "manager"),
            ("waiter", "waiter", "waiter1234", "2222", "waiter"),
            ("kitchen", "kitchen", "kitchen1234", "3333", "kitchen"),
            ("cashier", "cashier", "cashier1234", "4444", "cashier"),
        ]
        for username, first, password, pin, role in staff_defs:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"first_name": first.title(), "is_staff": True, "is_active": True},
            )
            user.set_password(password)
            user.is_active = True
            user.is_staff = True
            user.save()
            EmployeeProfile.objects.update_or_create(
                user=user,
                defaults={"restaurant": restaurant, "branch": branch, "role": role, "pin": pin},
            )

        for n in range(1, 9):
            col = (n - 1) % 4
            row = (n - 1) // 4
            Table.objects.update_or_create(
                floor=floor,
                number=n,
                defaults={
                    "label": f"T{n}",
                    "capacity": 4,
                    "plan_x": col * 22 + 4,
                    "plan_y": row * 22 + 8,
                    "plan_w": 12,
                    "plan_h": 14,
                },
            )

        menu = Menu.objects.filter(restaurant=restaurant, name_en="Main Menu").first()
        if menu is None:
            menu = Menu.objects.filter(restaurant=restaurant, name="Main Menu").first()
        if menu is None:
            menu = Menu.objects.create(
                restaurant=restaurant,
                name="Κύριο μενού",
                name_el="Κύριο μενού",
                name_en="Main Menu",
                is_active=True,
                is_draft=False,
            )
        else:
            _set_translated_name(menu, "Κύριο μενού", "Main Menu")
        if menu.is_draft:
            menu.is_draft = False
            menu.save()

        from django.db.models import Q

        Menu.objects.filter(restaurant=restaurant).filter(
            (Q(name_el__isnull=True) | Q(name_el=""))
            & (Q(name_en__isnull=True) | Q(name_en=""))
            & (Q(name__isnull=True) | Q(name=""))
        ).exclude(pk=menu.pk).delete()

        MenuCategory.objects.filter(menu=menu).filter(
            (Q(name_el__isnull=True) | Q(name_el=""))
            & (Q(name_en__isnull=True) | Q(name_en=""))
            & (Q(name__isnull=True) | Q(name=""))
        ).delete()

        allergen_i18n = {
            "Gluten": ("Γλουτένη", "Gluten"),
            "Dairy": ("Γαλακτοκομικά", "Dairy"),
            "Eggs": ("Αυγά", "Eggs"),
            "Nuts": ("Ξηροί καρποί", "Tree nuts"),
            "Peanuts": ("Φιστίκια", "Peanuts"),
            "Soy": ("Σόγια", "Soy"),
            "Fish": ("Ψάρι", "Fish"),
            "Shellfish": ("Οστρακοειδή", "Shellfish"),
            "Celery": ("Σέλινο", "Celery"),
            "Mustard": ("Μουστάρδα", "Mustard"),
            "Sesame": ("Σουσάμι", "Sesame"),
            "Sulphites": ("Θειώδη", "Sulphites"),
            "Lupin": ("Λούπινο", "Lupin"),
            "Molluscs": ("Μαλάκια", "Molluscs"),
        }
        allergens = {}
        for key, (name_el, name_en) in allergen_i18n.items():
            allergen = Allergen.objects.filter(name_en=name_en).first()
            if allergen is None:
                allergen = Allergen.objects.filter(name=key).first()
            if allergen is None:
                allergen = Allergen.objects.filter(name=name_en).first()
            if allergen is None:
                allergen = Allergen.objects.create(name=name_el, name_el=name_el, name_en=name_en)
            else:
                _set_translated_name(allergen, name_el, name_en)
            allergens[key] = allergen

        cats = [
            (
                ("Ορεκτικά", "Starters"),
                [
                    {
                        "name_el": "Χωριάτικη",
                        "name_en": "Greek Salad",
                        "description_el": "Ντομάτα, αγγούρι, φέτα, ελιές",
                        "description_en": "Tomato, cucumber, feta, olives",
                        "price": "8.50",
                        "vegetarian": True,
                        "vegan": True,
                        "calories": 180,
                        "protein": 4,
                        "carbs": 12,
                        "fat": 14,
                        "allergens": [],
                    },
                    {
                        "name_el": "Τζατζίκι",
                        "name_en": "Tzatziki",
                        "price": "5.00",
                        "vegetarian": True,
                        "calories": 120,
                        "allergens": ["Dairy"],
                    },
                ],
            ),
            (
                ("Κυρίως πιάτα", "Mains"),
                [
                    {
                        "name_el": "Μουσακάς",
                        "name_en": "Moussaka",
                        "price": "14.00",
                        "calories": 520,
                        "allergens": ["Gluten", "Dairy", "Eggs"],
                    },
                    {
                        "name_el": "Λαβράκι στη σχάρα",
                        "name_en": "Grilled Sea Bass",
                        "price": "18.50",
                        "calories": 380,
                        "allergens": ["Fish"],
                    },
                ],
            ),
            (
                ("Ποτά", "Drinks"),
                [
                    {"name_el": "Εσπρέσο", "name_en": "Espresso", "price": "2.50", "vegan": True, "calories": 5},
                    {
                        "name_el": "Τοπικό κρασί",
                        "name_en": "Local Wine",
                        "price": "6.00",
                        "vegan": True,
                        "calories": 125,
                        "allergens": ["Sulphites"],
                    },
                ],
            ),
        ]
        for i, ((cat_el, cat_en), items) in enumerate(cats):
            cat = MenuCategory.objects.filter(menu=menu, name_en=cat_en).first()
            if cat is None:
                cat = MenuCategory.objects.filter(menu=menu, name=cat_en).first()
            if cat is None:
                cat = MenuCategory.objects.create(
                    menu=menu,
                    name=cat_el,
                    name_el=cat_el,
                    name_en=cat_en,
                    sort_order=i,
                    is_active=True,
                )
            else:
                cat.sort_order = i
                cat.is_active = True
                _set_translated_name(cat, cat_el, cat_en)
            for j, spec in enumerate(items):
                item = MenuItem.objects.filter(category=cat, name_en=spec["name_en"]).first()
                if item is None:
                    item = MenuItem.objects.filter(category=cat, name=spec["name_en"]).first()
                if item is None:
                    item = MenuItem.objects.create(
                        category=cat,
                        name=spec["name_el"],
                        name_el=spec["name_el"],
                        name_en=spec["name_en"],
                        price=Decimal(spec["price"]),
                        is_available=True,
                        sort_order=j,
                        preparation_time=15,
                        is_vegetarian=spec.get("vegetarian", False),
                        is_vegan=spec.get("vegan", False),
                        calories=spec.get("calories"),
                        protein_g=spec.get("protein"),
                        carbohydrates_g=spec.get("carbs"),
                        fat_g=spec.get("fat"),
                    )
                else:
                    _set_translated_name(item, spec["name_el"], spec["name_en"])
                if spec.get("description_el") or spec.get("description_en"):
                    _set_translated_text(
                        item,
                        spec.get("description_el", ""),
                        spec.get("description_en", ""),
                    )
                item.is_vegetarian = spec.get("vegetarian", False)
                item.is_vegan = spec.get("vegan", False)
                if spec.get("calories"):
                    item.calories = spec["calories"]
                item.save()
                item.allergens.set([allergens[n] for n in spec.get("allergens", []) if n in allergens])

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write("Log in: waiter / waiter1234  PIN: 2222")
        self.stdout.write("Kitchen PIN: 3333")
