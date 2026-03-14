from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoice", "0003_invoice_etims_synced_at_invoice_tax_invoice_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="currency",
            field=models.CharField(default="KES", max_length=8),
        ),
        migrations.AddField(
            model_name="invoice",
            name="paid_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="receipt",
            name="currency",
            field=models.CharField(default="KES", max_length=8),
        ),
        migrations.AddField(
            model_name="receipt",
            name="reference",
            field=models.CharField(
                blank=True, default=None, max_length=120, null=True, unique=True
            ),
        ),
        migrations.AddIndex(
            model_name="invoice",
            index=models.Index(fields=["business"], name="invoice_business_idx"),
        ),
        migrations.AddIndex(
            model_name="invoice",
            index=models.Index(fields=["status"], name="invoice_status_idx"),
        ),
        migrations.AddIndex(
            model_name="invoice",
            index=models.Index(fields=["due_date"], name="invoice_due_date_idx"),
        ),
    ]
