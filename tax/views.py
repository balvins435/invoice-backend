from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from invoice.models import Invoice

from .models import TaxSubmission
from .serializers import TaxSubmissionSerializer, TaxSubmitRequestSerializer
from .services.etims_service import EtimsService


def _get_idempotency_key(request):
    key = request.headers.get("X-Idempotency-Key") or request.data.get("idempotency_key")
    key = (key or "").strip()
    return key or None


class TaxSubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TaxSubmissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = TaxSubmission.objects.filter(
            business__owner=self.request.user
        ).select_related("invoice", "business")

        invoice_id = self.request.query_params.get("invoice") or self.request.query_params.get("invoice_id")
        if invoice_id:
            queryset = queryset.filter(invoice_id=invoice_id)

        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)

        updated_after_raw = self.request.query_params.get("updated_after")
        if updated_after_raw:
            updated_after = parse_datetime(updated_after_raw)
            if updated_after is None:
                raise ValidationError({"updated_after": "Invalid datetime format. Use ISO-8601."})
            if timezone.is_naive(updated_after):
                updated_after = timezone.make_aware(updated_after, timezone.get_current_timezone())
            queryset = queryset.filter(updated_at__gt=updated_after)

        return queryset

    @action(detail=False, methods=["post"], url_path="submit-invoice")
    def submit_invoice(self, request):
        serializer = TaxSubmitRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        idempotency_key = _get_idempotency_key(request)
        if idempotency_key:
            existing = TaxSubmission.objects.filter(
                idempotency_key=idempotency_key,
                business__owner=request.user,
            ).select_related("invoice", "business").first()
            if existing:
                return Response(
                    {
                        **TaxSubmissionSerializer(existing).data,
                        "idempotent_replay": True,
                    },
                    status=status.HTTP_200_OK,
                )
            if TaxSubmission.objects.filter(idempotency_key=idempotency_key).exists():
                return Response(
                    {"error": "Idempotency key has already been used."},
                    status=status.HTTP_409_CONFLICT,
                )

        invoice = Invoice.objects.filter(
            id=serializer.validated_data["invoice_id"],
            business__owner=request.user,
        ).select_related("business").prefetch_related("items").first()

        if not invoice:
            return Response({"error": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)

        submission = EtimsService().submit_invoice(invoice, idempotency_key=idempotency_key)
        return Response(TaxSubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)
