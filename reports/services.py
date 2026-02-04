from django.db.models import Sum
from invoice.models import Invoice
from expenses.models import Expense


def monthly_report(business, month, year):
    invoices = Invoice.objects.filter(
        business=business,
        status='paid',
        issue_date__month=month,
        issue_date__year=year
    )

    expenses = Expense.objects.filter(
        business=business,
        expense_date__month=month,
        expense_date__year=year
    )

    total_revenue = invoices.aggregate(
        total=Sum('total_amount')
    )['total'] or 0

    total_expenses = expenses.aggregate(
        total=Sum('total_amount')
    )['total'] or 0

    vat_collected = invoices.aggregate(
        vat=Sum('tax_amount')
    )['vat'] or 0

    vat_paid = expenses.aggregate(
        vat=Sum('vat_amount')
    )['vat'] or 0

    profit = total_revenue - total_expenses

    return {
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "profit": profit,
        "vat_collected": vat_collected,
        "vat_paid": vat_paid,
        "vat_payable": vat_collected - vat_paid,
    }
