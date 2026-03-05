from django.contrib import admin

from .models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "invoice",
        "amount",
        "phone_number",
        "status",
        "mpesa_receipt_number",
        "created_at",
    )
    search_fields = (
        "reference",
        "invoice__invoice_number",
        "phone_number",
        "mpesa_receipt_number",
        "checkout_request_id",
    )
    list_filter = ("status", "created_at")
    readonly_fields = ("created_at", "updated_at")
