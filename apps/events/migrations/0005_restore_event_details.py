import importlib

from django.db import migrations

# While 0003 and 0004 were being deployed to production (2026-10-12, 05:40-05:55), four events were edited through
# the old dashboard, which didn't know the new fields: the Conclave and the Forum lost their copies before 0004 could
# move the details across, so they have empty details with everything pasted into `summary`; the Androth lecture got
# its pasted summary and its misread date (12 April) back; and the SIR session's title lost its closing quote. This
# restores each one from 0003's definitions, but only while it is still in that state, so anything staff have since
# entered in the new dashboard stays. The owner's start dates (except the misread one) and photos are kept.
OCTOBER = {
    event["slug"]: event for event in importlib.import_module("apps.events.migrations.0003_october_events").EVENTS
}

# Hand-entered slug on production -> the 0003 entry that holds its details.
EMPTY_DETAILS = {
    "kerala-demographic-conclave-navigating-p": "kerala-demographic-conclave-2026",
    "legislative-leadership-forum-good-govern": "legislative-leadership-forum-2026",
}
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
ANDROTH = "political-data-intelligence-in-the-digit"
SIR = "sir-update-today-decide-tomorrow-2025"


def restore(apps, schema_editor):
    Event = apps.get_model("events", "Event")

    for slug, source in EMPTY_DETAILS.items():
        event = Event.objects.filter(slug=slug, mode="").first()
        if event is not None:
            for field in DETAILS:
                setattr(event, field, OCTOBER[source][field])
            event.save()

    androth = Event.objects.filter(slug=ANDROTH, summary__startswith="Speaker:").first()
    if androth is not None:
        androth.summary = OCTOBER[ANDROTH]["summary"]
        androth.start_date = OCTOBER[ANDROTH]["start_date"]
        androth.save()

    sir = Event.objects.filter(slug=SIR).first()
    if sir is not None and not sir.title.endswith("”"):
        sir.title = OCTOBER[SIR]["title"]
        sir.save()


class Migration(migrations.Migration):
    dependencies = [("events", "0004_merge_hand_entered_duplicates")]

    operations = [migrations.RunPython(restore, migrations.RunPython.noop)]
