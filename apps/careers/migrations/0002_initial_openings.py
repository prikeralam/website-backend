from django.db import migrations
from django.utils import timezone

# The two roles PRI is hiring for (stakeholder meeting, 2026-10-08), both rolling: applications are welcome at
# any time and qualified people are hired when they apply. Staff refine the wording in the dashboard.
OPENINGS = [
    (
        "research-associate",
        "Research Associate",
        "Work with PRI's research team on data-driven studies of Kerala's social and economic questions.",
        1,
    ),
    (
        "data-analyst",
        "Data Analyst",
        "Clean, analyse and publish the datasets behind PRI's research and its public data repository.",
        2,
    ),
]


def create_openings(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    JobOpening = apps.get_model("careers", "JobOpening")
    # Openings need an owner; a fresh database without users simply gets none (staff add them later).
    owner = User.objects.filter(role="admin").order_by("id").first() or User.objects.order_by("id").first()
    if owner is None:
        return
    now = timezone.now()
    for slug, title, summary, order in OPENINGS:
        JobOpening.objects.get_or_create(
            slug=slug,
            defaults={
                "title": title,
                "summary": summary,
                "rolling": True,
                "display_order": order,
                "status": "published",
                "published_at": now,
                "created_by": owner,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("careers", "0001_initial"),
        ("accounts", "0003_user_must_change_password"),
    ]

    operations = [migrations.RunPython(create_openings, migrations.RunPython.noop)]
