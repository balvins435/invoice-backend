from django.conf import settings
from django.db import models
from django.utils.text import slugify


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
    display_name = models.CharField(max_length=255, blank=True, default="")
    slug = models.SlugField(max_length=80, blank=True, null=True)
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
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('owner', 'name')
        constraints = [
            models.UniqueConstraint(fields=["owner", "slug"], name="business_owner_slug_uniq"),
        ]

    def __str__(self):
        return self.name

    def _generate_unique_slug(self):
        base = slugify(self.display_name or self.name)[:70] or "business"
        slug = base
        counter = 2
        while Business.objects.filter(owner=self.owner, slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base}-{counter}"[:80]
            counter += 1
        return slug

    def save(self, *args, **kwargs):
        if not self.display_name:
            self.display_name = self.name
        if not self.slug:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)
