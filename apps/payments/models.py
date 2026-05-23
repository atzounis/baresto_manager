from django.db import models

from apps.common.models import TimeStampedModel


class PaymentRecord(TimeStampedModel):
    bill = models.ForeignKey("orders.Bill", on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20)
    reference = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Payment {self.amount} for bill #{self.bill_id}"
