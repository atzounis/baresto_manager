import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import TimeStampedModel
from apps.restaurants.legal_defaults import (
    ALLERGEN_NOTICE_EL,
    ALLERGEN_NOTICE_EN,
    COMPLAINT_SHEETS_NOTICE_EL,
    COMPLAINT_SHEETS_NOTICE_EN,
    CONSUMER_PAYMENT_NOTICE_EL,
    CONSUMER_PAYMENT_NOTICE_EN,
    PRICES_INCLUDE_TAXES_EL,
    PRICES_INCLUDE_TAXES_EN,
    PRODUCT_LEGEND_EL,
    PRODUCT_LEGEND_EN,
    SERVICE_CHARGE_NOTE_EL,
    SERVICE_CHARGE_NOTE_EN,
)


class Restaurant(TimeStampedModel):
    name = models.CharField(max_length=200)
    logo = models.ImageField(upload_to="restaurants/logos/", blank=True)
    menu_qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    primary_color = models.CharField(max_length=7, default="#2DB5A3")
    default_language = models.CharField(max_length=10, default="en")
    supported_languages = models.CharField(max_length=100, default="en")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class CompanyLegalProfile(TimeStampedModel):
    """Mandatory catalogue / digital-menu legal disclosures (GR + EN)."""

    restaurant = models.OneToOneField(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="legal_profile",
    )
    logo = models.ImageField(
        upload_to="restaurants/company_logos/",
        blank=True,
        help_text="Shown on guest QR menus with company details (not the Baresto app logo).",
    )
    trade_name_el = models.CharField(max_length=255, blank=True)
    trade_name_en = models.CharField(max_length=255, blank=True)
    address_el = models.TextField(blank=True)
    address_en = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    gemi_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="GEMI number",
        help_text="Γ.Ε.ΜΗ. — optional but recommended for digital menus.",
    )
    consumer_payment_notice_el = models.TextField(default=CONSUMER_PAYMENT_NOTICE_EL)
    consumer_payment_notice_en = models.TextField(default=CONSUMER_PAYMENT_NOTICE_EN)
    complaint_sheets_notice_el = models.TextField(default=COMPLAINT_SHEETS_NOTICE_EL)
    complaint_sheets_notice_en = models.TextField(default=COMPLAINT_SHEETS_NOTICE_EN)
    prices_include_taxes_el = models.TextField(default=PRICES_INCLUDE_TAXES_EL)
    prices_include_taxes_en = models.TextField(default=PRICES_INCLUDE_TAXES_EN)
    service_charge_enabled = models.BooleanField(default=False)
    service_charge_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Explicit cover/service charge in € (if applicable).",
    )
    service_charge_note_el = models.TextField(default=SERVICE_CHARGE_NOTE_EL, blank=True)
    service_charge_note_en = models.TextField(default=SERVICE_CHARGE_NOTE_EN, blank=True)
    allergen_notice_el = models.TextField(default=ALLERGEN_NOTICE_EL, blank=True)
    allergen_notice_en = models.TextField(default=ALLERGEN_NOTICE_EN, blank=True)
    product_legend_el = models.TextField(default=PRODUCT_LEGEND_EL, blank=True)
    product_legend_en = models.TextField(default=PRODUCT_LEGEND_EN, blank=True)
    show_on_guest_menu = models.BooleanField(default=True)

    class Meta:
        verbose_name = "company legal profile"
        verbose_name_plural = "company legal profiles"

    def __str__(self):
        return f"Legal profile — {self.restaurant.name}"

    def sync_from_branch(self, branch=None):
        """Prefill contact fields from the primary branch when empty."""
        if branch is None:
            branch = self.restaurant.branches.filter(is_active=True).first()
        if branch is None:
            return
        if not self.phone and branch.phone:
            self.phone = branch.phone
        if not self.address_el and branch.address:
            self.address_el = branch.address
        if not self.address_en and branch.address:
            self.address_en = branch.address
        if not self.trade_name_el:
            self.trade_name_el = self.restaurant.name
        if not self.trade_name_en:
            self.trade_name_en = self.restaurant.name


class Branch(TimeStampedModel):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="branches")
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    timezone = models.CharField(max_length=50, default="UTC")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "branches"

    def __str__(self):
        return f"{self.restaurant.name} — {self.name}"


class Floor(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="floors")
    name = models.CharField(max_length=100)
    layout_image = models.ImageField(upload_to="floors/", blank=True)

    def __str__(self):
        return f"{self.branch.name} / {self.name}"


class Table(models.Model):
    STATUS_CHOICES = [
        ("free", _("Free")),
        ("occupied", _("Occupied")),
        ("reserved", _("Reserved")),
        ("cleaning", _("Cleaning")),
    ]

    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name="tables")
    number = models.PositiveIntegerField()
    label = models.CharField(max_length=50, blank=True)
    capacity = models.PositiveIntegerField(default=4)
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    qr_code = models.ImageField(upload_to="qr_codes/", blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="free")
    plan_x = models.FloatField(
        null=True,
        blank=True,
        help_text="Horizontal position on floor plan (0–100%).",
    )
    plan_y = models.FloatField(
        null=True,
        blank=True,
        help_text="Vertical position on floor plan (0–100%).",
    )
    plan_w = models.FloatField(default=12, help_text="Width on floor plan (0–100%).")
    plan_h = models.FloatField(default=14, help_text="Height on floor plan (0–100%).")
    assigned_to = models.ForeignKey(
        "accounts.EmployeeProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tables",
    )

    class Meta:
        unique_together = [("floor", "number")]
        ordering = ["floor", "number"]

    def __str__(self):
        return self.label or f"Table {self.number}"

    @property
    def branch(self):
        return self.floor.branch

    @property
    def restaurant(self):
        return self.floor.branch.restaurant


class TableSession(TimeStampedModel):
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name="sessions")
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    cover_count = models.PositiveIntegerField(default=2)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Session {self.table} ({self.opened_at:%Y-%m-%d %H:%M})"


class OpeningHours(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="opening_hours")
    weekday = models.IntegerField()  # 0=Mon … 6=Sun
    opens_at = models.TimeField()
    closes_at = models.TimeField()
    is_closed = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "opening hours"
        unique_together = [("branch", "weekday")]

    def __str__(self):
        return f"{self.branch} day {self.weekday}"
