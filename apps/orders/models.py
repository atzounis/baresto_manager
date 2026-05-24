from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import SoftDeleteManager, TimeStampedModel


class Order(TimeStampedModel):
    STATUS_CHOICES = [
        ("open", _("Open")),
        ("confirmed", _("Confirmed")),
        ("preparing", _("Preparing")),
        ("partially_ready", _("Partially Ready")),
        ("ready", _("Ready")),
        ("served", _("Served")),
        ("bill_requested", _("Bill Requested")),
        ("paid", _("Paid")),
        ("cancelled", _("Cancelled")),
    ]

    session = models.ForeignKey(
        "restaurants.TableSession",
        on_delete=models.CASCADE,
        related_name="orders",
    )
    waiter = models.ForeignKey(
        "accounts.EmployeeProfile",
        on_delete=models.SET_NULL,
        null=True,
        related_name="orders",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    notes = models.TextField(blank=True)
    is_priority = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} — {self.session.table}"

    @property
    def branch(self):
        return self.session.table.branch

    @property
    def active_items(self):
        return self.items.filter(is_deleted=False)

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.active_items)

    @property
    def subtotal(self):
        return sum((item.line_total for item in self.active_items), Decimal("0"))

    def confirm(self):
        self.status = "confirmed"
        self.save(update_fields=["status", "updated_at"])


class OrderItem(TimeStampedModel):
    STATUS_CHOICES = [
        ("pending", _("Pending")),
        ("preparing", _("Preparing")),
        ("ready", _("Ready")),
        ("served", _("Served")),
    ]
    STATION_CHOICES = [
        ("kitchen", _("Kitchen")),
        ("bar", _("Bar")),
        ("grill", _("Grill")),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey("menus.MenuItem", on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    modifiers = models.ManyToManyField("menus.ModifierOption", blank=True)
    station = models.CharField(max_length=20, choices=STATION_CHOICES, default="kitchen")
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    is_deleted = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    served_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.quantity}x {self.menu_item.name}"

    @property
    def line_total(self):
        modifier_total = sum((m.price_delta for m in self.modifiers.all()), Decimal("0"))
        return (self.unit_price + modifier_total) * self.quantity

    def mark_preparing(self):
        self.status = "preparing"
        if not self.sent_at:
            self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at", "updated_at"])

    def mark_ready(self):
        self.status = "ready"
        self.ready_at = timezone.now()
        self.save(update_fields=["status", "ready_at", "updated_at"])


class Bill(TimeStampedModel):
    PAYMENT_METHODS = [
        ("cash", _("Cash")),
        ("card", _("Credit card")),
        ("split", _("Split")),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="bill")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default="cash")
    split_count = models.PositiveIntegerField(default=1)
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    receipt_printed = models.BooleanField(default=False)

    def __str__(self):
        return f"Bill for order #{self.order_id}"
