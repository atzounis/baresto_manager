from django import template
from django.utils.translation import gettext

from apps.menus.i18n import localized_name

register = template.Library()


@register.filter
def trans_label(value):
    """Translate a dynamic label (e.g. allergen or category name) if present in the catalog."""
    if value is None:
        return ""
    return gettext(str(value))


@register.filter
def localized_name_filter(obj, field="name"):
    """Menu/category/item label for the active UI language."""
    return localized_name(obj, base=field)
