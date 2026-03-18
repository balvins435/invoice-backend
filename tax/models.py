from django.db import models


class TaxSubmission(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SUBMITTED = "submitted"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_FAILED, "Failed"),
    )

    business = models.ForeignKey(
        "business.Business",
        on_delete=models.CASCADE,
        related_name="tax_submissions",
    )
    invoice = models.ForeignKey(
        "invoice.Invoice",
        on_delete=models.CASCADE,
        related_name="tax_submissions",
    )

    idempotency_key = models.CharField(
        max_length=120,
        unique=True,
        blank=True,
        null=True,
        default=None,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    tax_invoice_number = models.CharField(max_length=120, blank=True, default="")

    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")

    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["tax_invoice_number"])]

    def __str__(self):
        return f"Tax submission for {self.invoice.invoice_number} ({self.status})"
