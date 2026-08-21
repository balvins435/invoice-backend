from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import TaxSubmission
from .serializers import TaxSubmissionSerializer, TaxSubmitRequestSerializer
from .application.services import find_invoice, find_replay, idempotency_key_from, key_is_used, submit_invoice
from .selectors import filter_submissions, submissions_for_user


class TaxSubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TaxSubmissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return filter_submissions(submissions_for_user(self.request.user), self.request.query_params)

    @action(detail=False, methods=["post"], url_path="submit-invoice")
    def submit_invoice(self, request):
        serializer = TaxSubmitRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        idempotency_key = idempotency_key_from(request)
        if idempotency_key:
            existing = find_replay(idempotency_key, request.user)
            if existing:
                return Response(
                    {
                        **TaxSubmissionSerializer(existing).data,
                        "idempotent_replay": True,
                    },
                    status=status.HTTP_200_OK,
                )
            if key_is_used(idempotency_key):
                return Response(
                    {"error": "Idempotency key has already been used."},
                    status=status.HTTP_409_CONFLICT,
                )

        invoice = find_invoice(serializer.validated_data["invoice_id"], request.user)

        if not invoice:
            return Response({"error": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)

        submission = submit_invoice(invoice, idempotency_key)
        return Response(TaxSubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)
