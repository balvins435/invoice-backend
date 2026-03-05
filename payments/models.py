from uuid import uuid4

from django.db import models


def generate_payment_reference():
    return f"PAY-{uuid4().hex[:16].upper()}"


class PaymentTransaction(models.Model):
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    )

    business = models.ForeignKey(
        "business.Business",
        on_delete=models.CASCADE,
        related_name="payment_transactions",
    )
    invoice = models.ForeignKey(
        "invoice.Invoice",
        on_delete=models.CASCADE,
        related_name="payment_transactions",
    )

    reference = models.CharField(max_length=64, unique=True, default=generate_payment_reference)
    phone_number = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=8, default="KES")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    merchant_request_id = models.CharField(max_length=120, blank=True, default="")
    checkout_request_id = models.CharField(max_length=120, blank=True, default="")
    mpesa_receipt_number = models.CharField(max_length=120, blank=True, default="")

    result_code = models.CharField(max_length=20, blank=True, default="")
    result_description = models.TextField(blank=True, default="")

    raw_request = models.JSONField(default=dict, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    callback_payload = models.JSONField(default=dict, blank=True)

    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["checkout_request_id"]),
            models.Index(fields=["merchant_request_id"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.reference} ({self.status})"
