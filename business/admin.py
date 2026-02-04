# # business/admin.py
# from django.contrib import admin
# from .models import BusinessProfile, Client, BusinessSettings

# @admin.register(BusinessProfile)
# class BusinessProfileAdmin(admin.ModelAdmin):
#     list_display = ('business_name', 'user', 'city', 'country', 'is_active', 'created_at')
#     list_filter = ('is_active', 'country', 'created_at')
#     search_fields = ('business_name', 'user__email', 'tax_id', 'vat_number')
#     raw_id_fields = ('user',)
#     readonly_fields = ('created_at', 'updated_at')
#     fieldsets = (
#         ('Business Information', {
#             'fields': ('user', 'business_name', 'business_email', 'business_phone', 'website')
#         }),
#         ('Address', {
#             'fields': ('address_line1', 'address_line2', 'city', 'state', 'country', 'postal_code')
#         }),
#         ('Tax & Legal', {
#             'fields': ('tax_id', 'vat_number', 'vat_rate', 'currency', 'fiscal_year_start', 'timezone')
#         }),
#         ('Branding', {
#             'fields': ('logo', 'signature')
#         }),
#         ('Bank Details', {
#             'fields': ('bank_name', 'bank_account_name', 'bank_account_number', 'bank_branch', 'swift_code')
#         }),
#         ('Invoice Settings', {
#             'fields': ('invoice_prefix', 'invoice_start_number', 'receipt_prefix', 'receipt_start_number')
#         }),
#         ('Content', {
#             'fields': ('invoice_terms', 'invoice_notes')
#         }),
#         ('Status', {
#             'fields': ('is_active',)
#         }),
#         ('Metadata', {
#             'fields': ('created_at', 'updated_at'),
#             'classes': ('collapse',)
#         }),
#     )

# @admin.register(Client)
# class ClientAdmin(admin.ModelAdmin):
#     list_display = ('company_name', 'business', 'contact_person', 'email', 'is_active', 'created_at')
#     list_filter = ('is_active', 'category', 'is_vat_registered', 'created_at')
#     search_fields = ('company_name', 'contact_person', 'email', 'phone', 'client_code')
#     raw_id_fields = ('business',)
#     readonly_fields = ('client_code', 'created_at', 'updated_at')
#     fieldsets = (
#         ('Client Information', {
#             'fields': ('business', 'client_code', 'company_name', 'contact_person', 'email', 'phone', 'secondary_phone')
#         }),
#         ('Billing Address', {
#             'fields': ('billing_address', 'billing_city', 'billing_state', 'billing_country', 'billing_postal_code')
#         }),
#         ('Shipping Address', {
#             'fields': ('shipping_address', 'shipping_city', 'shipping_state', 'shipping_country', 'shipping_postal_code')
#         }),
#         ('Tax & Legal', {
#             'fields': ('tax_id', 'vat_number', 'category', 'is_vat_registered')
#         }),
#         ('Payment Terms', {
#             'fields': ('payment_terms_days', 'credit_limit')
#         }),
#         ('Status', {
#             'fields': ('is_active',)
#         }),
#         ('Notes', {
#             'fields': ('notes',)
#         }),
#         ('Metadata', {
#             'fields': ('created_at', 'updated_at'),
#             'classes': ('collapse',)
#         }),
#     )

# @admin.register(BusinessSettings)
# class BusinessSettingsAdmin(admin.ModelAdmin):
#     list_display = ('business', 'email_notifications', 'auto_backup', 'api_enabled')
#     list_filter = ('email_notifications', 'auto_backup', 'api_enabled')
#     search_fields = ('business__business_name',)
#     raw_id_fields = ('business',)
#     readonly_fields = ('api_key', 'created_at', 'updated_at')
#     fieldsets = (
#         ('Business', {
#             'fields': ('business',)
#         }),
#         ('Notification Settings', {
#             'fields': ('email_notifications', 'invoice_reminders', 'payment_receipts', 'low_stock_alerts')
#         }),
#         ('Invoice Settings', {
#             'fields': ('auto_generate_invoice_number', 'send_invoice_on_create', 'allow_partial_payments')
#         }),
#         ('Tax Settings', {
#             'fields': ('show_tax_on_invoice', 'inclusive_tax_pricing')
#         }),
#         ('Currency Settings', {
#             'fields': ('currency_symbol', 'currency_position', 'thousand_separator', 'decimal_separator')
#         }),
#         ('Display Settings', {
#             'fields': ('items_per_page', 'theme')
#         }),
#         ('Backup & Export', {
#             'fields': ('auto_backup', 'backup_frequency')
#         }),
#         ('API & Integration', {
#             'fields': ('api_enabled', 'api_key')
#         }),
#         ('Metadata', {
#             'fields': ('created_at', 'updated_at'),
#             'classes': ('collapse',)
#         }),
#     )