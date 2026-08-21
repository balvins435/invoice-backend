from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from .models import Invoice


def invoices_for_user(user):
    return Invoice.objects.filter(business__owner=user).select_related("business").prefetch_related("items", "receipts")


def filter_invoices(queryset, query_params):
    business_id = query_params.get("business") or query_params.get("business_id")
    if business_id:
        queryset = queryset.filter(business_id=business_id)
    if query_params.get("status"):
        queryset = queryset.filter(status=query_params["status"])
    if query_params.get("date_from"):
        queryset = queryset.filter(issue_date__gte=query_params["date_from"])
    if query_params.get("date_to"):
        queryset = queryset.filter(issue_date__lte=query_params["date_to"])
    if query_params.get("search"):
        search = query_params["search"]
        queryset = queryset.filter(Q(client_name__icontains=search) | Q(client_email__icontains=search) | Q(invoice_number__icontains=search))
    updated_after_raw = query_params.get("updated_after")
    if updated_after_raw:
        updated_after = parse_datetime(updated_after_raw)
        if updated_after is None:
            raise ValidationError({"updated_after": "Invalid datetime format. Use ISO-8601."})
        if timezone.is_naive(updated_after):
            updated_after = timezone.make_aware(updated_after, timezone.get_current_timezone())
        queryset = queryset.filter(updated_at__gt=updated_after)
    return queryset
