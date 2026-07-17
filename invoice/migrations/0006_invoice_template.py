from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0005_rename_invoice_business_idx_invoice_inv_busines_3069c7_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='template',
            field=models.CharField(
                choices=[
                    ('classic', 'Classic'),
                    ('modern', 'Modern'),
                    ('minimal', 'Minimal'),
                ],
                default='classic',
                max_length=20,
            ),
        ),
    ]
