from django.db import models


class WhatsAppMessage(models.Model):
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

    delivery_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    provider_message_id = models.CharField(max_length=120, blank=True, default="")
    provider_response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")

    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["delivery_status"])]

    def __str__(self):
        return f"WhatsApp {self.invoice.invoice_number} -> {self.phone_number}"
