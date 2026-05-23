from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import SoftDeleteManager, TimeStampedModel


class Allergen(models.Model):
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.name


class DietaryTag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=7, default="#22c55e")
    icon = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.name


class Menu(TimeStampedModel):
    restaurant = models.ForeignKey(
        "restaurants.Restaurant",
        on_delete=models.CASCADE,
        related_name="menus",
    )
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    is_draft = models.BooleanField(default=True)
    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    def publish(self):
        self.is_draft = False
        self.published_at = timezone.now()
        self.save(update_fields=["is_draft", "published_at", "updated_at"])


class MenuCategory(models.Model):
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="menu/categories/", blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "menu categories"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class MenuItem(TimeStampedModel):
    OIL_TYPE_CHOICES = [
        ("", _("—")),
        ("olive", _("Olive oil")),
        ("seed", _("Seed oil (e.g. sunflower)")),
        ("ev_olive", _("Extra virgin olive oil")),
    ]

    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="menu/items/", blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    happy_hour_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    preparation_time = models.PositiveIntegerField(default=15)
    is_available = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_vegetarian = models.BooleanField(default=False)
    is_vegan = models.BooleanField(default=False)
    is_frozen = models.BooleanField(
        default=False,
        help_text="Mandatory label for dishes with frozen meat, fish or seafood.",
    )
    oil_type = models.CharField(max_length=20, choices=OIL_TYPE_CHOICES, blank=True)
    origin_note_el = models.CharField(
        max_length=255,
        blank=True,
        help_text="Meat/seafood origin or PDO name (e.g. Φέτα Π.Ο.Π.).",
    )
    origin_note_en = models.CharField(max_length=255, blank=True)
    calories = models.PositiveIntegerField(null=True, blank=True, help_text="kcal per serving")
    protein_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    carbohydrates_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    fat_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    fiber_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    salt_g = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    allergens = models.ManyToManyField(Allergen, blank=True)
    dietary_tags = models.ManyToManyField(DietaryTag, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    archived_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    @property
    def restaurant(self):
        return self.category.menu.restaurant


class ModifierGroup(models.Model):
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name="modifier_groups")
    name = models.CharField(max_length=200)
    is_required = models.BooleanField(default=False)
    min_select = models.PositiveIntegerField(default=0)
    max_select = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.item.name} — {self.name}"


class ModifierOption(models.Model):
    group = models.ForeignKey(ModifierGroup, on_delete=models.CASCADE, related_name="options")
    name = models.CharField(max_length=200)
    price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return self.name


class AvailabilitySchedule(models.Model):
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name="schedules")
    weekday = models.IntegerField()
    available_from = models.TimeField()
    available_until = models.TimeField()

    def __str__(self):
        return f"{self.item.name} (day {self.weekday})"
