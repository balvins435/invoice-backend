from django.contrib import admin

from .models import TaxSubmission


@admin.register(TaxSubmission)
class TaxSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "invoice",
        "tax_invoice_number",
        "status",
        "submitted_at",
        "created_at",
    )
    search_fields = (
        "invoice__invoice_number",
        "tax_invoice_number",
    )
    list_filter = ("status", "created_at")
    readonly_fields = ("created_at", "updated_at")
