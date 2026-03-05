from django.conf import settings
from django.core import signing
from django.http import FileResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from invoice.models import Invoice
from invoice.utils import generate_invoice_pdf

from .models import WhatsAppMessage
from .serializers import SendWhatsAppInvoiceSerializer, WhatsAppMessageSerializer
from .services.whatsapp_service import WhatsAppService


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

        return queryset

    @action(detail=False, methods=["post"], url_path="send-invoice")
    def send_invoice(self, request):
        serializer = SendWhatsAppInvoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

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
