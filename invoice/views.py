import logging
import smtplib

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

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
        queryset = Invoice.objects.filter(
            business__owner=self.request.user
        ).select_related('business').prefetch_related('items', 'receipts')

        business_id = self.request.query_params.get("business") or self.request.query_params.get("business_id")
        if business_id:
            queryset = queryset.filter(business_id=business_id)

        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)

        date_from = self.request.query_params.get("date_from")
        if date_from:
            queryset = queryset.filter(issue_date__gte=date_from)

        date_to = self.request.query_params.get("date_to")
        if date_to:
            queryset = queryset.filter(issue_date__lte=date_to)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(client_name__icontains=search)
                | Q(client_email__icontains=search)
                | Q(invoice_number__icontains=search)
            )

        updated_after_raw = self.request.query_params.get("updated_after")
        if updated_after_raw:
            updated_after = parse_datetime(updated_after_raw)
            if updated_after is None:
                raise ValidationError({"updated_after": "Invalid datetime format. Use ISO-8601."})
            if timezone.is_naive(updated_after):
                updated_after = timezone.make_aware(updated_after, timezone.get_current_timezone())
            queryset = queryset.filter(updated_at__gt=updated_after)

        return queryset

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
