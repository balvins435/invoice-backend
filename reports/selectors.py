from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from business.models import Business
from expenses.models import Expense
from invoice.models import Invoice


def resolve_business(*, user, business_id=None, missing_message):
    queryset = Business.objects.filter(owner=user).order_by("id")
    if business_id:
        business = queryset.filter(id=business_id).first()
        if business: return business
        raise ValidationError({"business_id": "Invalid business for this user."})
    count = queryset.count()
    if count == 1: return queryset.first()
    if count == 0: return None
    raise ValidationError({"business_id": missing_message})


def dashboard_data(business):
    invoices = Invoice.objects.filter(business=business).select_related("business").prefetch_related("items", "receipts")
    expenses = Expense.objects.filter(business=business).select_related("category")
    income = invoices.filter(status="paid").aggregate(total=Sum("total_amount"))["total"] or 0
    expense_total = expenses.aggregate(total=Sum("total_amount"))["total"] or 0
    return {
        "invoices": invoices,
        "expenses": expenses,
        "total_income": income,
        "total_expenses": expense_total,
        "pending_invoices": invoices.filter(status__in=["sent", "partial"]).count(),
        "overdue_invoices": invoices.filter(~Q(status="paid"), due_date__lt=timezone.localdate()).count(),
        "total_clients": invoices.values("client_email").distinct().count(),
    }
