from apps.menus.models import Menu, MenuCategory
from apps.restaurants.models import CompanyLegalProfile


def get_guest_menu_context(*, restaurant, table=None):
    menu = (
        Menu.objects.filter(restaurant=restaurant, is_active=True, is_draft=False)
        .prefetch_related("categories")
        .first()
    )
    categories = []
    if menu:
        categories = (
            MenuCategory.objects.filter(menu=menu, is_active=True)
            .prefetch_related("items__allergens")
            .order_by("sort_order")
        )
    legal_profile = None
    try:
        legal_profile = restaurant.legal_profile
    except CompanyLegalProfile.DoesNotExist:
        pass

    return {
        "table": table,
        "restaurant": restaurant,
        "categories": categories,
        "legal_profile": legal_profile,
    }
