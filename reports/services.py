from calendar import month_name
from decimal import Decimal
from django.db.models import Sum, Count
from invoice.models import Invoice
from expenses.models import Expense


def _to_number(value):
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def monthly_report(business, month, year):
    invoices = Invoice.objects.filter(
        business=business,
        status__in=['sent', 'paid'],
        issue_date__month=month,
        issue_date__year=year
    )

    expenses = Expense.objects.filter(
        business=business,
        expense_date__month=month,
        expense_date__year=year
    )

    total_income = _to_number(invoices.aggregate(total=Sum('total_amount'))['total'])
    total_expenses = _to_number(expenses.aggregate(total=Sum('total_amount'))['total'])
    deductible_expenses = _to_number(
        expenses.filter(tax_deductible=True).aggregate(total=Sum('total_amount'))['total']
    )
    tax_collected = _to_number(invoices.aggregate(vat=Sum('tax_amount'))['vat'])
    tax_deductible = _to_number(
        expenses.filter(tax_deductible=True).aggregate(vat=Sum('vat_amount'))['vat']
    )
    tax_owed = tax_collected - tax_deductible
    net_profit = total_income - total_expenses

    return {
        "month": month_name[int(month)],
        "total_income": float(total_income),
        "total_expenses": float(total_expenses),
        "tax_owed": float(tax_owed),
        "deductible_expenses": float(deductible_expenses),
        "net_profit": float(net_profit),
        "invoice_count": invoices.aggregate(count=Count('id'))['count'] or 0,
        "expense_count": expenses.aggregate(count=Count('id'))['count'] or 0,
    }


def monthly_reports_for_year(business, year):
    return [monthly_report(business, month, year) for month in range(1, 13)]


def tax_summary(business, year, month=None):
    invoice_qs = Invoice.objects.filter(
        business=business,
        status__in=['sent', 'paid'],
        issue_date__year=year
    )
    expense_qs = Expense.objects.filter(
        business=business,
        expense_date__year=year
    )

    if month:
        invoice_qs = invoice_qs.filter(issue_date__month=month)
        expense_qs = expense_qs.filter(expense_date__month=month)

    total_tax_collected = _to_number(invoice_qs.aggregate(vat=Sum('tax_amount'))['vat'])
    total_tax_deductible = _to_number(
        expense_qs.filter(tax_deductible=True).aggregate(vat=Sum('vat_amount'))['vat']
    )
    net_tax_liability = total_tax_collected - total_tax_deductible

    by_month = []
    months_to_include = [int(month)] if month else list(range(1, 13))
    for month_num in months_to_include:
        month_invoices = invoice_qs.filter(issue_date__month=month_num)
        month_expenses = expense_qs.filter(expense_date__month=month_num, tax_deductible=True)
        month_collected = _to_number(month_invoices.aggregate(vat=Sum('tax_amount'))['vat'])
        month_deductible = _to_number(month_expenses.aggregate(vat=Sum('vat_amount'))['vat'])
        by_month.append({
            "month": month_name[month_num],
            "tax_collected": float(month_collected),
            "tax_deductible": float(month_deductible),
        })

    return {
        "total_tax_collected": float(total_tax_collected),
        "total_tax_deductible": float(total_tax_deductible),
        "net_tax_liability": float(net_tax_liability),
        "by_month": by_month,
    }
