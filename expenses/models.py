from django.db import models
from business.models import Business
from django.conf import settings


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
        default=0.00
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    expense_date = models.DateField()
    receipt = models.FileField(
        upload_to='receipts/',
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-expense_date']

    def save(self, *args, **kwargs):
        self.total_amount = self.amount + self.vat_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} - {self.amount}"
