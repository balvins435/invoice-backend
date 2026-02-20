import logging
import smtplib

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Invoice
from .serializers import InvoiceSerializer
from .permissions import IsBusinessOwner

from django.http import FileResponse
from .utils import generate_invoice_pdf

from .email_utils import InvoiceEmailError, send_invoice_email

logger = logging.getLogger(__name__)



class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessOwner]

    def get_queryset(self):
        return Invoice.objects.filter(
            business__owner=self.request.user
        )

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        invoice = self.get_object()
        invoice.status = 'paid'
        invoice.save()
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
