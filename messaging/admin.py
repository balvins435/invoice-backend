from django.contrib import admin

from .models import WhatsAppMessage


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = (
        "invoice",
        "phone_number",
        "delivery_status",
        "provider_message_id",
        "sent_at",
        "created_at",
    )
    search_fields = (
        "invoice__invoice_number",
        "phone_number",
        "provider_message_id",
    )
    list_filter = ("delivery_status", "created_at")
    readonly_fields = ("created_at", "updated_at")
