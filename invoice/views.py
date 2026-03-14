import logging
import smtplib

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone

from .models import Invoice, Receipt
from .serializers import InvoiceSerializer
from .permissions import IsBusinessOwner

from django.http import FileResponse
from .utils import generate_invoice_pdf, generate_receipt_pdf

from .email_utils import InvoiceEmailError, send_invoice_email

logger = logging.getLogger(__name__)



class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessOwner]

    def get_queryset(self):
        return Invoice.objects.filter(
            business__owner=self.request.user
        ).prefetch_related('items', 'receipts')

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status != 'paid':
            invoice.status = 'paid'
            invoice.paid_at = timezone.now()
            invoice.save(update_fields=['status', 'paid_at'])

        Receipt.objects.get_or_create(
            invoice=invoice,
            defaults={
                'payment_method': 'bank_transfer',
                'payment_date': timezone.localdate(),
                'amount_paid': invoice.total_amount,
                'currency': invoice.currency,
                'reference': f"manual-{invoice.invoice_number}",
                'notes': 'Auto-generated when invoice was marked as paid.',
            },
        )
        return Response({'status': 'Invoice marked as paid'})
    
# pdf generation    

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        invoice = self.get_object()
        pdf_buffer = generate_invoice_pdf(invoice)

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
            receipt = Receipt.objects.create(
                invoice=invoice,
                payment_method='bank_transfer',
                payment_date=timezone.localdate(),
                amount_paid=invoice.total_amount,
                currency=invoice.currency,
                reference=f"manual-{invoice.invoice_number}",
                notes='Auto-generated for an already paid invoice.',
            )

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
            send_invoice_email(invoice)
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

        invoice.status = 'sent'
        invoice.save()

        return Response({'status': 'Invoice sent'})
