# invoices/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import Invoice, InvoiceReminder


@receiver(post_save, sender=Invoice)
def create_invoice_pdf(sender, instance, created, **kwargs):
    """
    Generate PDF for invoice when it's marked as sent
    """
    if instance.status == 'sent' and not instance.pdf_file:
        # TODO: Generate PDF using reportlab or xhtml2pdf
        # This would be implemented with Celery for background processing
        pass


@receiver(post_save, sender=Invoice)
def send_invoice_email(sender, instance, created, **kwargs):
    """
    Send invoice email when marked as sent
    """
    if instance.status == 'sent' and instance.sent_via_email and instance.client:
        subject = f"Invoice {instance.invoice_number} from {instance.business.business_name}"
        
        # Render email template
        html_message = render_to_string('invoices/email_invoice.html', {
            'invoice': instance,
            'business': instance.business,
            'client': instance.client
        })
        
        # Send email (would use Celery in production)
        send_mail(
            subject=subject,
            message='',  # Plain text version
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[instance.client.email],
            html_message=html_message,
            fail_silently=True
        )


@receiver(pre_save, sender=Invoice)
def update_invoice_status(sender, instance, **kwargs):
    """
    Update invoice status based on payment
    """
    if instance.pk:
        old_instance = Invoice.objects.get(pk=instance.pk)
        
        # Check if payment was made
        if instance.amount_paid > old_instance.amount_paid:
            if instance.amount_paid >= instance.total_amount:
                instance.status = 'paid'
                if not instance.payment_date:
                    instance.payment_date = timezone.now().date()