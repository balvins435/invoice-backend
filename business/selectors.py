from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from .models import Business


def businesses_for_user(user):
    return Business.objects.filter(owner=user).order_by("id")


def filter_businesses(queryset, query_params):
    value = query_params.get("updated_after")
    if not value:
        return queryset
    parsed = parse_datetime(value)
    if parsed is None:
        raise ValidationError({"updated_after": "Invalid datetime format. Use ISO-8601."})
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return queryset.filter(updated_at__gt=parsed)
