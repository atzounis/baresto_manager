from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class EmployeeProfile(TimeStampedModel):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("manager", "Manager"),
        ("waiter", "Waiter"),
        ("cashier", "Cashier"),
        ("kitchen", "Kitchen"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )
    restaurant = models.ForeignKey(
        "restaurants.Restaurant",
        on_delete=models.CASCADE,
        related_name="staff",
    )
    branch = models.ForeignKey(
        "restaurants.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="waiter")
    pin = models.CharField(max_length=6, blank=True)
    avatar = models.ImageField(upload_to="staff/avatars/", blank=True)
    is_active_shift = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.role})"
