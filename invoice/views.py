import logging
import smtplib

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .serializers import InvoiceSerializer
from .permissions import IsBusinessOwner

from django.http import FileResponse
from .utils import generate_invoice_pdf, generate_receipt_pdf

from .email_utils import InvoiceEmailError
from .application.services import get_or_create_receipt, mark_invoice_paid, send_invoice
from .selectors import filter_invoices, invoices_for_user

logger = logging.getLogger(__name__)



class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessOwner]

    def get_queryset(self):
        return filter_invoices(invoices_for_user(self.request.user), self.request.query_params)

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        mark_invoice_paid(self.get_object())
        return Response({'status': 'Invoice marked as paid'})
    
# pdf generation    

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        invoice = self.get_object()
        template = request.query_params.get("template") or invoice.template
        pdf_buffer = generate_invoice_pdf(invoice, template=template)

        return FileResponse(
            pdf_buffer,
            as_attachment=True,
            filename=f"{invoice.invoice_number}.pdf"
        )

    @action(detail=True, methods=['get'])
    def receipt(self, request, pk=None):
        invoice = self.get_object()
        receipt = invoice.receipts.first()

        if not receipt:
            if invoice.status != 'paid':
                return Response(
                    {'error': 'Receipt is available only for paid invoices.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            receipt = get_or_create_receipt(invoice)

        pdf_buffer = generate_receipt_pdf(receipt)
        return FileResponse(
            pdf_buffer,
            as_attachment=True,
            filename=f"{receipt.receipt_number}.pdf"
        )
    
    @action(detail=True, methods=['post'])
    def send_email(self, request, pk=None):
        invoice = self.get_object()
        try:
            send_invoice(invoice)
        except smtplib.SMTPAuthenticationError:
            return Response(
                {'error': 'SMTP authentication failed. Check EMAIL_HOST_USER/EMAIL_HOST_PASSWORD.'},
                status=status.HTTP_502_BAD_GATEWAY
            )
        except smtplib.SMTPException as exc:
            return Response(
                {'error': f'Email delivery failed: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY
            )
        except InvoiceEmailError as exc:
            logger.warning("Invoice email delivery failed for invoice=%s: %s", invoice.id, exc)
            return Response(
                {'error': f'Email delivery failed: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY
            )

        return Response({'status': 'Invoice sent'})
