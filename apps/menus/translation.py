from modeltranslation.translator import TranslationOptions, register

from apps.menus.models import Allergen, Menu, MenuCategory, MenuItem, ModifierGroup, ModifierOption


@register(Menu)
class MenuTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(MenuCategory)
class MenuCategoryTranslationOptions(TranslationOptions):
    fields = ("name", "description")


@register(MenuItem)
class MenuItemTranslationOptions(TranslationOptions):
    fields = ("name", "description")


@register(ModifierGroup)
class ModifierGroupTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(ModifierOption)
class ModifierOptionTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Allergen)
class AllergenTranslationOptions(TranslationOptions):
    fields = ("name",)
