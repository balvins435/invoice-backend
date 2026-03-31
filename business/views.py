from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import permissions, viewsets
from rest_framework.exceptions import ValidationError

from .models import Business
from .serializers import BusinessSerializer
from .permissions import IsOwner


def _parse_updated_after(value: str | None):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        raise ValidationError({"updated_after": "Invalid datetime format. Use ISO-8601."})
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


class BusinessViewSet(viewsets.ModelViewSet):
    serializer_class = BusinessSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        queryset = Business.objects.filter(owner=self.request.user).order_by("id")
        updated_after = _parse_updated_after(self.request.query_params.get("updated_after"))
        if updated_after:
            queryset = queryset.filter(updated_at__gt=updated_after)
        return queryset

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
