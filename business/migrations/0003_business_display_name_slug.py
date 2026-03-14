from django.db import migrations, models
from django.utils.text import slugify


def populate_display_name_slug(apps, schema_editor):
    Business = apps.get_model("business", "Business")
    for business in Business.objects.all().order_by("id"):
        if not business.display_name:
            business.display_name = business.name
        if not business.slug:
            base = slugify(business.display_name or business.name)[:70] or "business"
            slug = base
            counter = 2
            while Business.objects.filter(owner_id=business.owner_id, slug=slug).exclude(pk=business.pk).exists():
                slug = f"{base}-{counter}"[:80]
                counter += 1
            business.slug = slug
        business.save(update_fields=["display_name", "slug"])


class Migration(migrations.Migration):

    dependencies = [
        ("business", "0002_business_logo_shape"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="display_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="business",
            name="slug",
            field=models.SlugField(blank=True, max_length=80, null=True),
        ),
        migrations.RunPython(populate_display_name_slug, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="business",
            constraint=models.UniqueConstraint(
                fields=["owner", "slug"], name="business_owner_slug_uniq"
            ),
        ),
    ]
