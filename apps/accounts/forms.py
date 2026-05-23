from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import EmployeeProfile
from apps.restaurants.models import Branch

User = get_user_model()


class StaffUserCreateForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        label=_("Username"),
        widget=forms.TextInput(attrs={"class": "menu-input", "autocomplete": "off"}),
    )
    first_name = forms.CharField(
        required=False,
        label=_("First name"),
        widget=forms.TextInput(attrs={"class": "menu-input"}),
    )
    last_name = forms.CharField(
        required=False,
        label=_("Last name"),
        widget=forms.TextInput(attrs={"class": "menu-input"}),
    )
    email = forms.EmailField(
        required=False,
        label=_("Email"),
        widget=forms.EmailInput(attrs={"class": "menu-input"}),
    )
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={"class": "menu-input", "autocomplete": "new-password"}),
    )
    role = forms.ChoiceField(
        choices=EmployeeProfile.ROLE_CHOICES,
        label=_("Role"),
        widget=forms.Select(attrs={"class": "menu-input"}),
    )
    pin = forms.CharField(
        max_length=6,
        required=False,
        label=_("PIN (quick login)"),
        widget=forms.TextInput(attrs={"class": "menu-input", "inputmode": "numeric", "pattern": "[0-9]*"}),
    )
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.none(),
        required=False,
        label=_("Branch"),
        widget=forms.Select(attrs={"class": "menu-input"}),
    )

    def __init__(self, *, restaurant, **kwargs):
        super().__init__(**kwargs)
        self.restaurant = restaurant
        self.fields["branch"].queryset = Branch.objects.filter(restaurant=restaurant, is_active=True).order_by(
            "name"
        )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(_("This username is already taken."))
        return username

    def clean_pin(self):
        pin = self.cleaned_data.get("pin", "").strip()
        if pin and (not pin.isdigit() or not (4 <= len(pin) <= 6)):
            raise forms.ValidationError(_("PIN must be 4–6 digits."))
        if pin and EmployeeProfile.objects.filter(restaurant=self.restaurant, pin=pin).exists():
            raise forms.ValidationError(_("This PIN is already used by another staff member."))
        return pin


class StaffUserUpdateForm(forms.Form):
    first_name = forms.CharField(
        required=False,
        label=_("First name"),
        widget=forms.TextInput(attrs={"class": "menu-input"}),
    )
    last_name = forms.CharField(
        required=False,
        label=_("Last name"),
        widget=forms.TextInput(attrs={"class": "menu-input"}),
    )
    email = forms.EmailField(
        required=False,
        label=_("Email"),
        widget=forms.EmailInput(attrs={"class": "menu-input"}),
    )
    role = forms.ChoiceField(
        choices=EmployeeProfile.ROLE_CHOICES,
        label=_("Role"),
        widget=forms.Select(attrs={"class": "menu-input"}),
    )
    pin = forms.CharField(
        max_length=6,
        required=False,
        label=_("PIN (quick login)"),
        widget=forms.TextInput(attrs={"class": "menu-input", "inputmode": "numeric"}),
    )
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.none(),
        required=False,
        label=_("Branch"),
        widget=forms.Select(attrs={"class": "menu-input"}),
    )
    is_active = forms.BooleanField(
        required=False,
        label=_("Account active"),
    )
    new_password = forms.CharField(
        required=False,
        label=_("New password"),
        help_text=_("Leave blank to keep the current password."),
        widget=forms.PasswordInput(attrs={"class": "menu-input", "autocomplete": "new-password"}),
    )

    def __init__(self, *, profile, **kwargs):
        super().__init__(**kwargs)
        self.profile = profile
        user = profile.user
        self.fields["branch"].queryset = Branch.objects.filter(
            restaurant=profile.restaurant, is_active=True
        ).order_by("name")
        self.fields["first_name"].initial = user.first_name
        self.fields["last_name"].initial = user.last_name
        self.fields["email"].initial = user.email
        self.fields["role"].initial = profile.role
        self.fields["pin"].initial = profile.pin
        self.fields["branch"].initial = profile.branch_id
        self.fields["is_active"].initial = user.is_active

    def clean_pin(self):
        pin = self.cleaned_data.get("pin", "").strip()
        if pin and (not pin.isdigit() or not (4 <= len(pin) <= 6)):
            raise forms.ValidationError(_("PIN must be 4–6 digits."))
        if pin:
            exists = EmployeeProfile.objects.filter(
                restaurant=self.profile.restaurant, pin=pin
            ).exclude(pk=self.profile.pk)
            if exists.exists():
                raise forms.ValidationError(_("This PIN is already used by another staff member."))
        return pin
