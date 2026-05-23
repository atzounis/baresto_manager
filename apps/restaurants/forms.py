from django import forms
from django.utils.translation import gettext_lazy as _

from apps.restaurants.models import CompanyLegalProfile, Floor, Table


class FloorForm(forms.ModelForm):
    class Meta:
        model = Floor
        fields = ["name"]
        labels = {"name": _("Floor name")}
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "menu-input", "placeholder": _("e.g. Terrace, 1st floor")}
            ),
        }


class TableForm(forms.ModelForm):
    class Meta:
        model = Table
        fields = ["floor", "label", "number", "capacity"]
        labels = {
            "floor": _("Floor"),
            "label": _("Table name (optional)"),
            "number": _("Table number"),
            "capacity": _("Seats"),
        }
        widgets = {
            "floor": forms.Select(attrs={"class": "menu-input"}),
            "label": forms.TextInput(attrs={"class": "menu-input", "placeholder": _("e.g. Terrace 3")}),
            "number": forms.NumberInput(attrs={"class": "menu-input", "min": 1}),
            "capacity": forms.NumberInput(attrs={"class": "menu-input", "min": 1, "max": 99}),
        }

    def __init__(self, *, branch, **kwargs):
        super().__init__(**kwargs)
        floor_field = self.fields["floor"]
        floor_field.queryset = Floor.objects.filter(branch=branch).order_by("name")
        floor_field.label_from_instance = lambda obj: obj.name
        self.fields["number"].required = False
        self.fields["label"].required = False
        if not self.instance.pk:
            self.fields["capacity"].initial = 4

    def clean(self):
        cleaned = super().clean()
        floor = cleaned.get("floor")
        number = cleaned.get("number")
        if floor and number:
            exists = Table.objects.filter(floor=floor, number=number)
            if self.instance.pk:
                exists = exists.exclude(pk=self.instance.pk)
            if exists.exists():
                raise forms.ValidationError(
                    _("Table number %(number)s already exists on this floor.") % {"number": number}
                )
        return cleaned


class CompanyLegalProfileForm(forms.ModelForm):
    class Meta:
        model = CompanyLegalProfile
        fields = [
            "logo",
            "trade_name_el",
            "trade_name_en",
            "address_el",
            "address_en",
            "phone",
            "gemi_number",
            "consumer_payment_notice_el",
            "consumer_payment_notice_en",
            "complaint_sheets_notice_el",
            "complaint_sheets_notice_en",
            "prices_include_taxes_el",
            "prices_include_taxes_en",
            "service_charge_enabled",
            "service_charge_amount",
            "service_charge_note_el",
            "service_charge_note_en",
            "allergen_notice_el",
            "allergen_notice_en",
            "product_legend_el",
            "product_legend_en",
            "show_on_guest_menu",
        ]
        widgets = {
            "trade_name_el": forms.TextInput(attrs={"class": "menu-input"}),
            "trade_name_en": forms.TextInput(attrs={"class": "menu-input"}),
            "address_el": forms.Textarea(attrs={"rows": 2, "class": "menu-input"}),
            "address_en": forms.Textarea(attrs={"rows": 2, "class": "menu-input"}),
            "phone": forms.TextInput(attrs={"class": "menu-input"}),
            "gemi_number": forms.TextInput(attrs={"class": "menu-input"}),
            "consumer_payment_notice_el": forms.Textarea(attrs={"rows": 3, "class": "menu-input"}),
            "consumer_payment_notice_en": forms.Textarea(attrs={"rows": 3, "class": "menu-input"}),
            "complaint_sheets_notice_el": forms.Textarea(attrs={"rows": 2, "class": "menu-input"}),
            "complaint_sheets_notice_en": forms.Textarea(attrs={"rows": 2, "class": "menu-input"}),
            "prices_include_taxes_el": forms.Textarea(attrs={"rows": 2, "class": "menu-input"}),
            "prices_include_taxes_en": forms.Textarea(attrs={"rows": 2, "class": "menu-input"}),
            "service_charge_amount": forms.NumberInput(attrs={"class": "menu-input", "step": "0.01"}),
            "service_charge_note_el": forms.Textarea(attrs={"rows": 2, "class": "menu-input"}),
            "service_charge_note_en": forms.Textarea(attrs={"rows": 2, "class": "menu-input"}),
            "allergen_notice_el": forms.Textarea(attrs={"rows": 2, "class": "menu-input"}),
            "allergen_notice_en": forms.Textarea(attrs={"rows": 2, "class": "menu-input"}),
            "product_legend_el": forms.Textarea(attrs={"rows": 2, "class": "menu-input"}),
            "product_legend_en": forms.Textarea(attrs={"rows": 2, "class": "menu-input"}),
        }
        labels = {
            "logo": _("Company logo (guest menu)"),
            "trade_name_el": _("Trade name (Greek)"),
            "trade_name_en": _("Trade name (English)"),
            "address_el": _("Full address (Greek)"),
            "address_en": _("Full address (English)"),
            "phone": _("Phone"),
            "gemi_number": _("GEMI no."),
            "consumer_payment_notice_el": _("Consumer payment notice (Greek)"),
            "consumer_payment_notice_en": _("Consumer payment notice (English)"),
            "complaint_sheets_notice_el": _("Complaint sheets notice (Greek)"),
            "complaint_sheets_notice_en": _("Complaint sheets notice (English)"),
            "prices_include_taxes_el": _("Tax inclusion notice (Greek)"),
            "prices_include_taxes_en": _("Tax inclusion notice (English)"),
            "service_charge_enabled": _("Cover / service charge applies"),
            "service_charge_amount": _("Service charge (€)"),
            "service_charge_note_el": _("Service charge note (Greek)"),
            "service_charge_note_en": _("Service charge note (English)"),
            "allergen_notice_el": _("Allergen policy (Greek)"),
            "allergen_notice_en": _("Allergen policy (English)"),
            "product_legend_el": _("Product symbols legend (Greek)"),
            "product_legend_en": _("Product symbols legend (English)"),
            "show_on_guest_menu": _("Show legal block on guest QR menu"),
        }
