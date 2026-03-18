from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from invoice.models import Invoice

from .models import PaymentTransaction
from .serializers import (
    ManualConfirmationSerializer,
    PaymentTransactionSerializer,
    STKPushRequestSerializer,
)
from .services.mpesa_service import MpesaService


def _get_idempotency_key(request):
    key = request.headers.get("X-Idempotency-Key") or request.data.get("idempotency_key")
    key = (key or "").strip()
    return key or None


class PaymentTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = PaymentTransaction.objects.filter(
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

    @action(detail=False, methods=["post"], url_path="initiate-stk")
    def initiate_stk(self, request):
        serializer = STKPushRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        idempotency_key = _get_idempotency_key(request)
        if idempotency_key:
            existing = PaymentTransaction.objects.filter(
                idempotency_key=idempotency_key,
                business__owner=request.user,
            ).select_related("invoice", "business").first()
            if existing:
                return Response(
                    {
                        "transaction": PaymentTransactionSerializer(existing).data,
                        "provider_response": existing.raw_response,
                        "idempotent_replay": True,
                    },
                    status=status.HTTP_200_OK,
                )
            if PaymentTransaction.objects.filter(idempotency_key=idempotency_key).exists():
                return Response(
                    {"error": "Idempotency key has already been used."},
                    status=status.HTTP_409_CONFLICT,
                )

        invoice = Invoice.objects.filter(
            id=serializer.validated_data["invoice_id"],
            business__owner=request.user,
        ).select_related("business").first()

        if not invoice:
            return Response({"error": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)

        if invoice.status == "paid":
            return Response(
                {"error": "Invoice is already paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mpesa_service = MpesaService()
        transaction, provider_response = mpesa_service.initiate_stk_push(
            invoice=invoice,
            phone_number=serializer.validated_data["phone_number"],
            amount=serializer.validated_data.get("amount"),
            idempotency_key=idempotency_key,
        )

        response_status = status.HTTP_201_CREATED
        if transaction.status == PaymentTransaction.STATUS_FAILED:
            response_status = status.HTTP_502_BAD_GATEWAY

        return Response(
            {
                "transaction": PaymentTransactionSerializer(transaction).data,
                "provider_response": provider_response,
            },
            status=response_status,
        )

    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        transaction = self.get_object()

        serializer = ManualConfirmationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated = MpesaService.confirm_transaction(
            transaction,
            success=serializer.validated_data["success"],
            result_code=serializer.validated_data["result_code"],
            result_description=serializer.validated_data["result_description"],
            receipt_number=serializer.validated_data["mpesa_receipt_number"],
            callback_payload=request.data,
        )

        return Response(PaymentTransactionSerializer(updated).data)


class MpesaCallbackAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        payload = request.data

        stk_callback = (payload.get("Body") or {}).get("stkCallback") or payload.get("stkCallback") or {}
        checkout_request_id = stk_callback.get("CheckoutRequestID") or payload.get("checkout_request_id")

        if not checkout_request_id:
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"}, status=status.HTTP_200_OK)

        transaction = PaymentTransaction.objects.filter(
            checkout_request_id=checkout_request_id
        ).order_by("-id").first()

        if not transaction:
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"}, status=status.HTTP_200_OK)

        result_code = stk_callback.get("ResultCode", payload.get("result_code", 1))
        result_desc = stk_callback.get("ResultDesc", payload.get("result_description", ""))
        success = str(result_code) == "0"

        receipt_number = payload.get("mpesa_receipt_number", "")
        metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])
        if not isinstance(metadata, list):
            metadata = []
        for item in metadata:
            if item.get("Name") == "MpesaReceiptNumber":
                receipt_number = item.get("Value", "")
                break

        MpesaService.confirm_transaction(
            transaction,
            success=success,
            result_code=result_code,
            result_description=result_desc,
            receipt_number=receipt_number,
            callback_payload=payload,
        )

        return Response({"ResultCode": 0, "ResultDesc": "Accepted"}, status=status.HTTP_200_OK)
