from django.db import models


class WhatsAppMessage(models.Model):
    TYPE_MANUAL_INVOICE = "manual_invoice"
    TYPE_AUTO_PAID = "auto_paid"

    MESSAGE_TYPE_CHOICES = (
        (TYPE_MANUAL_INVOICE, "Manual Invoice"),
        (TYPE_AUTO_PAID, "Auto Paid Notification"),
    )

    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
    )

    business = models.ForeignKey(
        "business.Business",
        on_delete=models.CASCADE,
        related_name="whatsapp_messages",
    )
    invoice = models.ForeignKey(
        "invoice.Invoice",
        on_delete=models.CASCADE,
        related_name="whatsapp_messages",
    )

    phone_number = models.CharField(max_length=20)
    message_text = models.TextField()
    invoice_link = models.URLField()
    message_type = models.CharField(
        max_length=30,
        choices=MESSAGE_TYPE_CHOICES,
        default=TYPE_MANUAL_INVOICE,
    )
    idempotency_key = models.CharField(
        max_length=120,
        unique=True,
        blank=True,
        null=True,
        default=None,
    )
    attempt_count = models.PositiveIntegerField(default=0)

    delivery_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    provider_message_id = models.CharField(max_length=120, blank=True, default="")
    provider_response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")

    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["delivery_status"]),
            models.Index(fields=["message_type"]),
        ]

    def __str__(self):
        return f"WhatsApp {self.invoice.invoice_number} -> {self.phone_number}"
