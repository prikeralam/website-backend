from django.db import migrations

# events/0003 matched the two events it knew had been entered by hand on production, but the Conclave and the Forum
# had been entered by hand too, under these slugs, so 0003 created a second copy of each. This keeps the hand-entered
# rows (their slugs may already be shared, and they carry the photos and the owner's chosen start date), gives them
# the structured details from the copies, and deletes the copies. Where a hand-entered row doesn't exist (staging,
# fresh databases), nothing changes.
PAIRS = [
    ("kerala-demographic-conclave-navigating-p", "kerala-demographic-conclave-2026"),
    ("legislative-leadership-forum-good-govern", "legislative-leadership-forum-2026"),
]
DETAILS = [
    "title",
    "summary",
    "location",
    "mode",
    "start_time",
    "end_time",
    "date_note",
    "collaborators",
    "speakers",
    "focus_areas",
]


def merge(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    EventImage = apps.get_model("events", "EventImage")
    for kept_slug, copy_slug in PAIRS:
        kept = Event.objects.filter(slug=kept_slug).first()
        copy = Event.objects.filter(slug=copy_slug).first()
        if kept is None or copy is None:
            continue
        for field in DETAILS:
            setattr(kept, field, getattr(copy, field))
        if not kept.image and not kept.image_url:
            kept.image, kept.image_url = copy.image, copy.image_url
        kept.save()
        EventImage.objects.filter(event=copy).update(event=kept)
        copy.delete()


class Migration(migrations.Migration):
    dependencies = [("events", "0003_october_events")]

    operations = [migrations.RunPython(merge, migrations.RunPython.noop)]
