from django.db import models

from apps.common.models import TimeStampedModel


class Notification(TimeStampedModel):
    recipient = models.ForeignKey(
        "accounts.EmployeeProfile",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
