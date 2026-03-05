from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from invoice.models import Invoice

from .models import TaxSubmission
from .serializers import TaxSubmissionSerializer, TaxSubmitRequestSerializer
from .services.etims_service import EtimsService


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

        return queryset

    @action(detail=False, methods=["post"], url_path="submit-invoice")
    def submit_invoice(self, request):
        serializer = TaxSubmitRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invoice = Invoice.objects.filter(
            id=serializer.validated_data["invoice_id"],
            business__owner=request.user,
        ).select_related("business").prefetch_related("items").first()

        if not invoice:
            return Response({"error": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)

        submission = EtimsService().submit_invoice(invoice)
        return Response(TaxSubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)
