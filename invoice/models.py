from decimal import Decimal

from django.db import models
from django.db.models import Sum
from business.models import Business


def generate_invoice_number(business):
    last_invoice = Invoice.objects.filter(
        business=business
    ).order_by('-id').first()

    if not last_invoice:
        return "INV-0001"

    last_number = int(last_invoice.invoice_number.split('-')[-1])
    return f"INV-{last_number + 1:04d}"


def generate_receipt_number():
    last_receipt = Receipt.objects.order_by('-id').first()
    if not last_receipt:
        return "RCT-0001"
    last_number = int(last_receipt.receipt_number.split('-')[-1])
    return f"RCT-{last_number + 1:04d}"


class Invoice(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
    )

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='invoices'
    )

    invoice_number = models.CharField(
        max_length=50,
        editable=False
    )

    client_name = models.CharField(max_length=255)
    client_email = models.EmailField()

    issue_date = models.DateField()
    due_date = models.DateField()

    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=8, default="KES")
    tax_invoice_number = models.CharField(max_length=120, blank=True, default='')
    etims_synced_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='draft'
    )

    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('business', 'invoice_number')
        indexes = [
            models.Index(fields=['business']),
            models.Index(fields=['status']),
            models.Index(fields=['due_date']),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.client_name}"

    @property
    def amount_paid(self):
        total = self.receipts.aggregate(total=Sum("amount_paid")).get("total")
        return total or Decimal("0.00")

    @property
    def balance_due(self):
        balance = self.total_amount - self.amount_paid
        return balance if balance > Decimal("0.00") else Decimal("0.00")


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        related_name='items',
        on_delete=models.CASCADE
    )
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.description


class Receipt(models.Model):
    PAYMENT_METHOD_CHOICES = (
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('card', 'Card'),
        ('other', 'Other'),
    )

    invoice = models.ForeignKey(
        Invoice,
        related_name='receipts',
        on_delete=models.CASCADE
    )
    receipt_number = models.CharField(max_length=50, unique=True, editable=False)
    payment_method = models.CharField(
        max_length=30,
        choices=PAYMENT_METHOD_CHOICES,
        default='bank_transfer'
    )
    payment_date = models.DateField()
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=8, default="KES")
    reference = models.CharField(max_length=120, unique=True, blank=True, null=True, default=None)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = generate_receipt_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receipt_number} - {self.invoice.invoice_number}"
