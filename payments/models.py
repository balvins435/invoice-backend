from django.db import models

class Payment(models.Model):
    business=models.ForeignKey('Business', on_delete=models.CASCADE)
    invoice=models.ForeignKey('Invoice', on_delete=models.CASCADE)

    amount=models.DecimalField(max_digits=10, decimal_places=2)
