from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from modeltranslation.forms import TranslationModelForm

from apps.menus.i18n import localized_name
from apps.menus.models import Allergen, Menu, MenuCategory, MenuItem


def _named_queryset(model):
    """Rows that have at least one non-empty translated name."""
    return model.objects.filter(
        Q(name_el__gt="")
        | Q(name_en__gt="")
        | Q(name__gt="")
    )


def _apply_single_choice_default(form, field_name):
    """Pre-select the only option so the blank '---------' row is not shown."""
    if form.is_bound:
        return
    field = form.fields.get(field_name)
    if field is None:
        return
    if form.initial.get(field_name) or field.initial:
        return
    queryset = field.queryset
    if queryset.count() == 1:
        pk = queryset.first().pk
        form.initial[field_name] = pk
        field.initial = pk


class TranslatedModelChoiceField(forms.ModelChoiceField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("empty_label", None)
        super().__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        return localized_name(obj)


class TranslatedAllergenChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return localized_name(obj)


class MenuItemForm(TranslationModelForm):
    """Expose name_el/name_en and description_* — TranslationModelForm hides TranslationFields."""

    _translation_fields = ("name_el", "name_en", "description_el", "description_en")

    category = TranslatedModelChoiceField(
        queryset=MenuCategory.objects.none(),
        label=_("Category"),
        widget=forms.Select(attrs={"class": "menu-input"}),
    )
    allergens = TranslatedAllergenChoiceField(
        queryset=Allergen.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("Contains allergens"),
    )

    class Meta:
        model = MenuItem
        fields = [
            "category",
            "name",
            "name_el",
            "name_en",
            "description",
            "description_el",
            "description_en",
            "image",
            "price",
            "happy_hour_price",
            "preparation_time",
            "sort_order",
            "is_available",
            "is_featured",
            "is_vegetarian",
            "is_vegan",
            "is_frozen",
            "oil_type",
            "origin_note_el",
            "origin_note_en",
            "calories",
            "protein_g",
            "carbohydrates_g",
            "fat_g",
            "fiber_g",
            "salt_g",
            "allergens",
        ]
        labels = {
            "category": _("Category"),
            "name_el": _("Name (Greek)"),
            "name_en": _("Name (English)"),
            "description_el": _("Description (Greek)"),
            "description_en": _("Description (English)"),
            "image": _("Photo"),
            "price": _("Price (€)"),
            "happy_hour_price": _("Happy hour price (optional)"),
            "preparation_time": _("Prep time (min)"),
            "sort_order": _("Sort order"),
            "is_available": _("Available"),
            "is_featured": _("Featured"),
            "is_vegetarian": _("Vegetarian"),
            "is_vegan": _("Vegan"),
            "is_frozen": _("Frozen product (*)"),
            "oil_type": _("Oil used (salads/frying)"),
            "origin_note_el": _("Origin / PDO note (Greek)"),
            "origin_note_en": _("Origin / PDO note (English)"),
            "calories": _("Calories (kcal)"),
            "protein_g": _("Protein (g)"),
            "carbohydrates_g": _("Carbohydrates (g)"),
            "fat_g": _("Fat (g)"),
            "fiber_g": _("Fiber (g)"),
            "salt_g": _("Salt (g)"),
        }
        widgets = {
            "description_el": forms.Textarea(
                attrs={"rows": 3, "class": "menu-input", "placeholder": _("Short description in Greek")}
            ),
            "description_en": forms.Textarea(
                attrs={"rows": 3, "class": "menu-input", "placeholder": _("Short description in English")}
            ),
            "name_el": forms.TextInput(attrs={"class": "menu-input"}),
            "name_en": forms.TextInput(attrs={"class": "menu-input"}),
            "price": forms.NumberInput(attrs={"class": "menu-input", "step": "0.01"}),
            "happy_hour_price": forms.NumberInput(attrs={"class": "menu-input", "step": "0.01"}),
            "preparation_time": forms.NumberInput(attrs={"class": "menu-input"}),
            "sort_order": forms.NumberInput(attrs={"class": "menu-input"}),
            "calories": forms.NumberInput(attrs={"class": "menu-input"}),
            "protein_g": forms.NumberInput(attrs={"class": "menu-input", "step": "0.1"}),
            "carbohydrates_g": forms.NumberInput(attrs={"class": "menu-input", "step": "0.1"}),
            "fat_g": forms.NumberInput(attrs={"class": "menu-input", "step": "0.1"}),
            "fiber_g": forms.NumberInput(attrs={"class": "menu-input", "step": "0.1"}),
            "salt_g": forms.NumberInput(attrs={"class": "menu-input", "step": "0.1"}),
            "oil_type": forms.Select(attrs={"class": "menu-input"}),
            "origin_note_el": forms.TextInput(attrs={"class": "menu-input"}),
            "origin_note_en": forms.TextInput(attrs={"class": "menu-input"}),
        }

    def __init__(self, *args, restaurant=None, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self._translation_fields:
            if field_name in self.base_fields:
                self.fields[field_name] = self.base_fields[field_name]
        self.fields.pop("name", None)
        self.fields.pop("description", None)
        if restaurant is not None:
            self.fields["category"].queryset = (
                _named_queryset(MenuCategory)
                .filter(menu__restaurant=restaurant, is_active=True)
                .select_related("menu")
                .order_by("sort_order", "name_el", "name_en")
            )
        self.fields["allergens"].queryset = _named_queryset(Allergen).order_by("name_el", "name_en")
        _apply_single_choice_default(self, "category")


class MenuCategoryForm(TranslationModelForm):
    _translation_fields = ("name_el", "name_en", "description_el", "description_en")

    menu = TranslatedModelChoiceField(
        queryset=Menu.objects.none(),
        label=_("Menu"),
        widget=forms.Select(attrs={"class": "menu-input"}),
    )

    class Meta:
        model = MenuCategory
        fields = [
            "menu",
            "name",
            "name_el",
            "name_en",
            "description",
            "description_el",
            "description_en",
            "sort_order",
            "is_active",
        ]
        labels = {
            "menu": _("Menu"),
            "name_el": _("Name (Greek)"),
            "name_en": _("Name (English)"),
            "description_el": _("Description (Greek)"),
            "description_en": _("Description (English)"),
            "sort_order": _("Sort order"),
            "is_active": _("Active"),
        }
        widgets = {
            "name_el": forms.TextInput(attrs={"class": "menu-input"}),
            "name_en": forms.TextInput(attrs={"class": "menu-input"}),
            "description_el": forms.Textarea(attrs={"rows": 2, "class": "menu-input"}),
            "description_en": forms.Textarea(attrs={"rows": 2, "class": "menu-input"}),
            "sort_order": forms.NumberInput(attrs={"class": "menu-input"}),
        }

    def __init__(self, *args, restaurant=None, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self._translation_fields:
            if field_name in self.base_fields:
                self.fields[field_name] = self.base_fields[field_name]
        self.fields.pop("name", None)
        self.fields.pop("description", None)
        if restaurant is not None:
            self.fields["menu"].queryset = (
                _named_queryset(Menu)
                .filter(restaurant=restaurant, is_active=True)
                .order_by("name_el", "name_en")
            )
            _apply_single_choice_default(self, "menu")
