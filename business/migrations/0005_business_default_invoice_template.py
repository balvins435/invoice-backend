from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('business', '0004_business_updated_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='default_invoice_template',
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
