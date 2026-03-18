from django.conf import settings
from django.core import signing
from django.http import FileResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from invoice.models import Invoice
from invoice.utils import generate_invoice_pdf

from .models import WhatsAppMessage
from .serializers import SendWhatsAppInvoiceSerializer, WhatsAppMessageSerializer
from .services.whatsapp_service import WhatsAppService


def _get_idempotency_key(request):
    key = request.headers.get("X-Idempotency-Key") or request.data.get("idempotency_key")
    key = (key or "").strip()
    return key or None


class WhatsAppMessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WhatsAppMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = WhatsAppMessage.objects.filter(
            business__owner=self.request.user
        ).select_related("invoice", "business")

        invoice_id = self.request.query_params.get("invoice") or self.request.query_params.get("invoice_id")
        if invoice_id:
            queryset = queryset.filter(invoice_id=invoice_id)

        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(delivery_status=status_value)

        updated_after_raw = self.request.query_params.get("updated_after")
        if updated_after_raw:
            updated_after = parse_datetime(updated_after_raw)
            if updated_after is None:
                raise ValidationError({"updated_after": "Invalid datetime format. Use ISO-8601."})
            if timezone.is_naive(updated_after):
                updated_after = timezone.make_aware(updated_after, timezone.get_current_timezone())
            queryset = queryset.filter(updated_at__gt=updated_after)

        return queryset

    @action(detail=False, methods=["post"], url_path="send-invoice")
    def send_invoice(self, request):
        serializer = SendWhatsAppInvoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        idempotency_key = _get_idempotency_key(request)
        if idempotency_key:
            existing = WhatsAppMessage.objects.filter(
                idempotency_key=idempotency_key,
                business__owner=request.user,
            ).select_related("invoice", "business").first()
            if existing:
                return Response(
                    {
                        **WhatsAppMessageSerializer(existing).data,
                        "idempotent_replay": True,
                    },
                    status=status.HTTP_200_OK,
                )
            if WhatsAppMessage.objects.filter(idempotency_key=idempotency_key).exists():
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

        message = WhatsAppService().send_invoice(
            invoice=invoice,
            phone_number=serializer.validated_data["phone_number"],
            request_obj=request,
            custom_message=serializer.validated_data.get("message", ""),
            idempotency_key=idempotency_key,
        )

        if message.delivery_status == WhatsAppMessage.STATUS_SENT and invoice.status == "draft":
            invoice.status = "sent"
            invoice.save(update_fields=["status"])

        status_code = status.HTTP_201_CREATED if message.delivery_status == WhatsAppMessage.STATUS_SENT else status.HTTP_502_BAD_GATEWAY
        return Response(WhatsAppMessageSerializer(message).data, status=status_code)


class PublicInvoicePDFView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, token):
        try:
            invoice = WhatsAppService.resolve_invoice_from_token(
                token=token,
                max_age_seconds=getattr(settings, "WHATSAPP_LINK_TTL_SECONDS", 7 * 24 * 60 * 60),
            )
        except signing.SignatureExpired:
            return Response({"error": "This invoice link has expired."}, status=status.HTTP_410_GONE)
        except (signing.BadSignature, Invoice.DoesNotExist):
            return Response({"error": "Invalid invoice link."}, status=status.HTTP_404_NOT_FOUND)

        pdf_buffer = generate_invoice_pdf(invoice)
        return FileResponse(
            pdf_buffer,
            as_attachment=True,
            filename=f"{invoice.invoice_number}.pdf",
        )
