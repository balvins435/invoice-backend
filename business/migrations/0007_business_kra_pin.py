from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('business', '0006_alter_business_default_invoice_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='kra_pin',
            field=models.CharField(blank=True, default='', help_text='KRA PIN printed in the supplier block of an eTIMS tax invoice.', max_length=20),
        ),
        migrations.AlterField(
            model_name='business',
            name='default_invoice_template',
            field=models.CharField(choices=[('classic', 'Classic'), ('modern', 'Modern'), ('minimal', 'Minimal'), ('letterhead', 'Letterhead'), ('etims', 'eTIMS Tax Invoice')], default='classic', max_length=20),
        ),
    ]