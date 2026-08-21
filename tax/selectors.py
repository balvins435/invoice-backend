from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError
from .models import TaxSubmission

def submissions_for_user(user):
    return TaxSubmission.objects.filter(business__owner=user).select_related("invoice", "business")

def filter_submissions(queryset, params):
    for field in ("business", "invoice"):
        value = params.get(field) or params.get(f"{field}_id")
        if value: queryset = queryset.filter(**{f"{field}_id": value})
    if params.get("status"): queryset = queryset.filter(status=params["status"])
    value = params.get("updated_after")
    if value:
        parsed = parse_datetime(value)
        if parsed is None: raise ValidationError({"updated_after": "Invalid datetime format. Use ISO-8601."})
        if timezone.is_naive(parsed): parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        queryset = queryset.filter(updated_at__gt=parsed)
    return queryset
