import logging

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .serializers import InvoiceSerializer
from .permissions import IsBusinessOwner

from django.http import FileResponse
from .utils import generate_invoice_pdf, generate_receipt_pdf

from .email_utils import EmailConfigurationError, InvoiceEmailError
from .email_utils import email_diagnostics as email_diagnostics_report
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
        except EmailConfigurationError as exc:
            logger.error("Invoice email is not configured (invoice=%s): %s", invoice.pk, exc)
            return Response(
                {
                    'error': f'Email delivery is not configured: {exc}',
                    'code': 'email_not_configured',
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except InvoiceEmailError as exc:
            logger.error("Invoice email delivery failed (invoice=%s): %s", invoice.pk, exc)
            return Response(
                {
                    'error': f'Email delivery failed: {exc}',
                    'code': 'email_delivery_failed',
                },
                status=status.HTTP_502_BAD_GATEWAY
            )

        return Response({'status': 'Invoice sent'})

    @action(detail=False, methods=['get'], url_path='email-diagnostics')
    def email_diagnostics(self, request):
        """Report how outbound email is configured (no secrets are exposed)."""
        probe = str(request.query_params.get('probe', '')).strip().lower() in {'1', 'true', 'yes'}
        return Response(email_diagnostics_report(probe=probe))
