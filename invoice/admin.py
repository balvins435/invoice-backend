# # invoices/admin.py
# from django.contrib import admin
# from .models import Invoice, InvoiceItem, InvoiceTemplate, InvoiceReminder


# class InvoiceItemInline(admin.TabularInline):
#     model = InvoiceItem
#     extra = 1
#     readonly_fields = ('line_total', 'vat_amount', 'total_with_vat')
#     fields = (
#         'product_service', 'description', 'quantity', 'unit_price',
#         'unit', 'vat_rate', 'discount_percentage', 'line_total',
#         'vat_amount', 'total_with_vat'
#     )


# @admin.register(Invoice)
# class InvoiceAdmin(admin.ModelAdmin):
#     list_display = (
#         'invoice_number', 'business', 'client', 'status',
#         'issue_date', 'due_date', 'total_amount', 'amount_paid',
#         'balance_due', 'is_overdue'
#     )
#     list_filter = ('status', 'payment_method', 'issue_date', 'due_date', 'business')
#     search_fields = ('invoice_number', 'client__company_name', 'reference')
#     readonly_fields = (
#         'invoice_number', 'subtotal', 'vat_amount', 'discount_amount',
#         'total_amount', 'balance_due', 'payment_status', 'is_overdue',
#         'overdue_days', 'created_at', 'updated_at'
#     )
#     fieldsets = (
#         ('Invoice Information', {
#             'fields': (
#                 'business', 'client', 'invoice_number', 'reference', 'status'
#             )
#         }),
#         ('Dates', {
#             'fields': ('issue_date', 'due_date', 'payment_date')
#         }),
#         ('Payment Information', {
#             'fields': (
#                 'payment_method', 'payment_terms', 'currency'
#             )
#         }),
#         ('Financials', {
#             'fields': (
#                 'subtotal', 'vat_amount', 'discount_type', 'discount_value',
#                 'discount_amount', 'shipping_charge', 'adjustment',
#                 'total_amount', 'amount_paid', 'balance_due'
#             )
#         }),
#         ('Content', {
#             'fields': ('title', 'notes', 'terms')
#         }),
#         ('Files & Tracking', {
#             'fields': (
#                 'pdf_file', 'sent_via_email', 'viewed_at', 'reminder_sent'
#             )
#         }),
#         ('Status Info', {
#             'fields': ('payment_status', 'is_overdue', 'overdue_days'),
#             'classes': ('collapse',)
#         }),
#         ('Metadata', {
#             'fields': ('created_at', 'updated_at'),
#             'classes': ('collapse',)
#         }),
#     )
#     inlines = [InvoiceItemInline]
    
#     def is_overdue(self, obj):
#         return obj.is_overdue
#     is_overdue.boolean = True
#     is_overdue.short_description = 'Overdue'


# @admin.register(InvoiceItem)
# class InvoiceItemAdmin(admin.ModelAdmin):
#     list_display = (
#         'invoice', 'description', 'quantity', 'unit_price',
#         'line_total', 'vat_amount', 'total_with_vat'
#     )
#     list_filter = ('item_type', 'invoice__business')
#     search_fields = ('description', 'invoice__invoice_number', 'original_product_name')
#     readonly_fields = ('line_total', 'vat_amount', 'total_with_vat', 'created_at', 'updated_at')


# @admin.register(InvoiceTemplate)
# class InvoiceTemplateAdmin(admin.ModelAdmin):
#     list_display = ('name', 'business', 'template_type', 'is_default')
#     list_filter = ('template_type', 'is_default', 'business')
#     search_fields = ('name', 'business__business_name')
#     readonly_fields = ('created_at', 'updated_at')


# @admin.register(InvoiceReminder)
# class InvoiceReminderAdmin(admin.ModelAdmin):
#     list_display = ('invoice', 'reminder_type', 'days_before_after', 'sent', 'sent_at')
#     list_filter = ('reminder_type', 'sent')
#     search_fields = ('invoice__invoice_number', 'subject')
#     readonly_fields = ('sent_at', 'created_at', 'updated_at')