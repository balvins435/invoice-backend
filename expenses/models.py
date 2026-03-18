from django.db import models
from business.models import Business
from django.conf import settings
from decimal import Decimal


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Expense(models.Model):
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='expenses'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    vat_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_deductible = models.BooleanField(default=True)

    expense_date = models.DateField()
    receipt = models.FileField(
        upload_to='receipts/',
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-expense_date']

    def save(self, *args, **kwargs):
        amount = self.amount if isinstance(self.amount, Decimal) else Decimal(str(self.amount or 0))
        vat = self.vat_amount if isinstance(self.vat_amount, Decimal) else Decimal(str(self.vat_amount or 0))
        self.total_amount = amount + vat
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} - {self.amount}"
