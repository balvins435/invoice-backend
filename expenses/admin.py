# # expenses/admin.py
# from django.contrib import admin
# from .models import Expense, ExpenseCategory, RecurringExpense


# @admin.register(ExpenseCategory)
# class ExpenseCategoryAdmin(admin.ModelAdmin):
#     list_display = ('name', 'business', 'category_type', 'monthly_budget', 'is_active')
#     list_filter = ('category_type', 'is_active', 'business')
#     search_fields = ('name', 'business__business_name')
#     readonly_fields = ('created_at', 'updated_at')
#     fieldsets = (
#         ('Category Information', {
#             'fields': ('business', 'name', 'description', 'category_type')
#         }),
#         ('Styling', {
#             'fields': ('color',)
#         }),
#         ('VAT Settings', {
#             'fields': ('default_vat_rate', 'default_is_vat_claimable')
#         }),
#         ('Budget', {
#             'fields': ('monthly_budget',)
#         }),
#         ('Status', {
#             'fields': ('is_active',)
#         }),
#         ('Metadata', {
#             'fields': ('created_at', 'updated_at'),
#             'classes': ('collapse',)
#         }),
#     )


# @admin.register(Expense)
# class ExpenseAdmin(admin.ModelAdmin):
#     list_display = (
#         'expense_number', 'business', 'vendor', 'category',
#         'expense_date', 'total_amount', 'status', 'is_vat_claimable',
#         'vat_claimed'
#     )
#     list_filter = ('status', 'is_vat_claimable', 'vat_claimed', 'category', 'business')
#     search_fields = ('expense_number', 'vendor', 'description')
#     readonly_fields = (
#         'expense_number', 'vat_amount', 'total_amount', 'has_receipt',
#         'amount_in_business_currency', 'vat_amount_in_business_currency',
#         'total_amount_in_business_currency', 'created_at', 'updated_at'
#     )
#     fieldsets = (
#         ('Expense Information', {
#             'fields': (
#                 'business', 'category', 'invoice', 'expense_number',
#                 'vendor', 'vendor_tax_id', 'description'
#             )
#         }),
#         ('Dates', {
#             'fields': ('expense_date', 'payment_date')
#         }),
#         ('Amounts', {
#             'fields': (
#                 'amount', 'currency', 'exchange_rate', 'vat_rate',
#                 'vat_amount', 'total_amount'
#             )
#         }),
#         ('VAT Information', {
#             'fields': ('is_vat_claimable', 'vat_claimed', 'vat_claim_date')
#         }),
#         ('Payment', {
#             'fields': ('payment_method', 'payment_reference')
#         }),
#         ('Receipt', {
#             'fields': ('receipt_image', 'receipt_file', 'has_receipt')
#         }),
#         ('Status', {
#             'fields': ('status', 'is_business_expense', 'is_recurring', 'recurring_frequency')
#         }),
#         ('Approval', {
#             'fields': ('approved_by', 'approved_at')
#         }),
#         ('Notes', {
#             'fields': ('notes', 'internal_notes')
#         }),
#         ('Creator', {
#             'fields': ('created_by',)
#         }),
#         ('Calculated Fields', {
#             'fields': (
#                 'amount_in_business_currency', 'vat_amount_in_business_currency',
#                 'total_amount_in_business_currency'
#             ),
#             'classes': ('collapse',)
#         }),
#         ('Metadata', {
#             'fields': ('created_at', 'updated_at'),
#             'classes': ('collapse',)
#         }),
#     )


# @admin.register(RecurringExpense)
# class RecurringExpenseAdmin(admin.ModelAdmin):
#     list_display = ('name', 'business', 'vendor', 'amount', 'frequency', 'is_active')
#     list_filter = ('frequency', 'is_active', 'business')
#     search_fields = ('name', 'vendor', 'description')
#     readonly_fields = ('last_generated', 'next_generation', 'created_at', 'updated_at')
#     fieldsets = (
#         ('Recurring Expense Information', {
#             'fields': ('business', 'category', 'name', 'description', 'vendor')
#         }),
#         ('Amounts', {
#             'fields': ('amount', 'vat_rate')
#         }),
#         ('Scheduling', {
#             'fields': (
#                 'frequency', 'start_date', 'end_date',
#                 'day_of_month', 'day_of_week'
#             )
#         }),
#         ('Payment', {
#             'fields': ('payment_method', 'is_vat_claimable')
#         }),
#         ('Status', {
#             'fields': ('is_active', 'last_generated', 'next_generation')
#         }),
#         ('Notes', {
#             'fields': ('notes',)
#         }),
#         ('Metadata', {
#             'fields': ('created_at', 'updated_at'),
#             'classes': ('collapse',)
#         }),
#     )