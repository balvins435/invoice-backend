from django.conf import settings
from django.db import models


class Business(models.Model):
    LOGO_SHAPE_RECT = "rect"
    LOGO_SHAPE_CIRCLE = "circle"
    LOGO_SHAPE_CHOICES = (
        (LOGO_SHAPE_RECT, "Rect"),
        (LOGO_SHAPE_CIRCLE, "Circle"),
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='businesses'
    )
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    logo = models.ImageField(upload_to='logos/', null=True, blank=True)
    logo_shape = models.CharField(
        max_length=12,
        choices=LOGO_SHAPE_CHOICES,
        default=LOGO_SHAPE_RECT,
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=16.00
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('owner', 'name')

    def __str__(self):
        return self.name
