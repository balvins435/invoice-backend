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
from .selectors import filter_messages, messages_for_user
from .application.services import find_invoice, find_replay, idempotency_key_from, key_is_used, send_invoice_message


class WhatsAppMessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WhatsAppMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return filter_messages(messages_for_user(self.request.user), self.request.query_params)

    @action(detail=False, methods=["post"], url_path="send-invoice")
    def send_invoice(self, request):
        serializer = SendWhatsAppInvoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        idempotency_key = idempotency_key_from(request)
        if idempotency_key:
            existing = find_replay(idempotency_key, request.user)
            if existing:
                return Response(
                    {
                        **WhatsAppMessageSerializer(existing).data,
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

        message = send_invoice_message(
            invoice=invoice,
            phone_number=serializer.validated_data["phone_number"],
            request=request,
            custom_message=serializer.validated_data.get("message", ""),
            idempotency_key=idempotency_key,
        )

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
