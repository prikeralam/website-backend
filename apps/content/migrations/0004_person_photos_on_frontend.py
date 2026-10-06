"""Point seeded person photos at the current frontend instead of the retired Vercel prototype.

The demo seed stored photo URLs under https://pri-website-pink.vercel.app/people/..., files that the frontend
still ships in its own public/people/ folder. Each environment's FRONTEND_URL serves them, so the prefix is
rewritten to it. Photos set to any other URL are left alone.
"""

from django.conf import settings
from django.db import migrations
from django.db.models import Value
from django.db.models.functions import Concat, Substr

OLD_PREFIX = "https://pri-website-pink.vercel.app/people/"


def rewrite_photo_urls(apps, schema_editor):
    PersonProfile = apps.get_model("content", "PersonProfile")
    PersonProfile.objects.filter(photo_url__startswith=OLD_PREFIX).update(
        photo_url=Concat(Value(f"{settings.FRONTEND_URL}/people/"), Substr("photo_url", len(OLD_PREFIX) + 1))
    )


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0003_alter_contentblock_options_alter_document_options_and_more"),
    ]

    operations = [
        migrations.RunPython(rewrite_photo_urls, migrations.RunPython.noop),
    ]
