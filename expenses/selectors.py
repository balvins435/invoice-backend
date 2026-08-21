from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from .models import Expense


def expenses_for_user(user):
    return Expense.objects.filter(business__owner=user).select_related("business", "category")


def filter_expenses(queryset, params):
    business_id = params.get("business") or params.get("business_id")
    if business_id: queryset = queryset.filter(business_id=business_id)
    category = params.get("category")
    if category: queryset = queryset.filter(category__name=category.lower())
    deductible = params.get("tax_deductible")
    if deductible in ["true", "false"]: queryset = queryset.filter(tax_deductible=deductible == "true")
    start = params.get("date_from") or params.get("start_date")
    end = params.get("date_to") or params.get("end_date")
    if start: queryset = queryset.filter(expense_date__gte=start)
    if end: queryset = queryset.filter(expense_date__lte=end)
    if params.get("search"):
        search = params["search"]
        queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search))
    value = params.get("updated_after")
    if value:
        parsed = parse_datetime(value)
        if parsed is None: raise ValidationError({"updated_after": "Invalid datetime format. Use ISO-8601."})
        if timezone.is_naive(parsed): parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        queryset = queryset.filter(updated_at__gt=parsed)
    return queryset
