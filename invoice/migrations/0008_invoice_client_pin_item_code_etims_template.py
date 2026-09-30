from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0007_alter_invoice_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='client_pin',
            field=models.CharField(blank=True, default='', help_text='Buyer KRA PIN printed in the customer block of an eTIMS tax invoice.', max_length=20),
        ),
        migrations.AddField(
            model_name='invoiceitem',
            name='code',
            field=models.CharField(blank=True, default='', help_text='Stock or item code printed on an eTIMS tax invoice.', max_length=64),
        ),
        migrations.AlterField(
            model_name='invoice',
            name='template',
            field=models.CharField(blank=True, choices=[('classic', 'Classic'), ('modern', 'Modern'), ('minimal', 'Minimal'), ('letterhead', 'Letterhead'), ('etims', 'eTIMS Tax Invoice')], default='', help_text='Blank inherits the business default template.', max_length=20),
        ),
    ]