# Seeds the canonical 8-value theme vocabulary confirmed on the live site's filter UIs.
# See docs/erd/pri_platform_schema.sql:82-83 and docs/erd/README.md:86-98.

from django.db import migrations

THEMES = [
    ("education", "Education"),
    ("employment", "Employment"),
    ("economics", "Economics"),
    ("public-finance", "Public Finance"),
    ("health", "Health"),
    ("governance", "Governance"),
    ("demography", "Demography"),
    ("migration", "Migration"),
]


def seed_themes(apps, schema_editor):
    Theme = apps.get_model("taxonomy", "Theme")
    for slug, name in THEMES:
        Theme.objects.get_or_create(slug=slug, defaults={"name": name})


def unseed_themes(apps, schema_editor):
    Theme = apps.get_model("taxonomy", "Theme")
    Theme.objects.filter(slug__in=[slug for slug, _ in THEMES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("taxonomy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_themes, unseed_themes),
    ]
