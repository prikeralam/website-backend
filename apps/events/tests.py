import importlib
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Event, EventImage

User = get_user_model()


class EventTests(APITestCase):
    def setUp(self):
        self.editor = User.objects.create_user(username="editor1", password="pw12345", role="editor")
        self.client.force_authenticate(self.editor)

    def create(self, **extra):
        data = {"slug": "launch", "title": "Launch", "start_date": "2026-11-01", **extra}
        return self.client.post("/api/v1/events/", data, format="json")

    def test_creates_an_event_by_default(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["kind"], "event")

    def test_campaigns_can_run_until_an_end_date(self):
        response = self.create(kind="campaign", end_date="2026-12-31")
        self.assertEqual((response.data["kind"], response.data["end_date"]), ("campaign", "2026-12-31"))

    def test_end_date_cannot_come_before_the_start(self):
        response = self.create(end_date="2026-10-01")
        self.assertEqual(response.status_code, 400)
        self.assertIn("end_date", response.data)

    def test_registration_link_must_be_https(self):
        response = self.create(registration_url="http://forms.example/register")
        self.assertEqual(response.status_code, 400)
        self.assertIn("registration_url", response.data)

    def test_public_list_is_newest_first_and_filters_by_kind(self):
        rows = [("a", "event", "2026-01-01"), ("b", "campaign", "2026-06-01"), ("c", "event", "2026-03-01")]
        for slug, kind, start in rows:
            Event.objects.create(
                slug=slug,
                kind=kind,
                title=slug,
                start_date=start,
                status="published",
                published_at=timezone.now(),
                created_by=self.editor,
            )
        self.client.force_authenticate(None)
        listed = self.client.get("/api/v1/events/").data["results"]
        self.assertEqual([e["slug"] for e in listed], ["b", "c", "a"])
        only_events = self.client.get("/api/v1/events/?kind=event").data["results"]
        self.assertEqual([e["slug"] for e in only_events], ["c", "a"])


class EventDetailsTests(APITestCase):
    def setUp(self):
        self.editor = User.objects.create_user(username="editor2", password="pw12345", role="editor")
        self.client.force_authenticate(self.editor)

    def create(self, **extra):
        data = {"slug": "forum", "title": "Forum", "start_date": "2026-11-01", **extra}
        return self.client.post("/api/v1/events/", data, format="json")

    def test_details_round_trip(self):
        response = self.create(
            mode="hybrid",
            start_time="09:30",
            end_time="17:00",
            date_note="December 2026 (3rd or 4th week)",
            collaborators=["SAFI Institutions"],
            speakers=["Lead speaker: Muhammed Thufail", "Presided by: Dr. Anees Vavad"],
            focus_areas=["Data-driven governance: A data-based analysis"],
        )
        self.assertEqual(response.status_code, 201, response.data)
        data = self.client.get("/api/v1/events/forum/").data
        self.assertEqual((data["mode"], data["start_time"], data["end_time"]), ("hybrid", "09:30:00", "17:00:00"))
        self.assertEqual(data["speakers"][1], "Presided by: Dr. Anees Vavad")
        self.assertEqual(data["date_note"], "December 2026 (3rd or 4th week)")
        self.assertEqual(data["images"], [])

    def test_curly_quotes_survive_json_and_multipart(self):
        title = "SIR: “Update Today, Decide Tomorrow” – Students’ Union"
        self.assertEqual(self.create(title=title).data["title"], title)
        response = self.client.post(
            "/api/v1/events/", {"slug": "multi", "title": title, "start_date": "2026-11-01"}, format="multipart"
        )
        self.assertEqual(response.data["title"], title)

    def test_end_time_cannot_come_before_the_start_on_one_day(self):
        response = self.create(start_time="11:00", end_time="10:00")
        self.assertEqual(response.status_code, 400)
        self.assertIn("end_time", response.data)
        # Over several days an earlier end time is fine.
        response = self.create(start_time="11:00", end_time="10:00", end_date="2026-11-02")
        self.assertEqual(response.status_code, 201, response.data)

    def test_lists_are_trimmed_and_refuse_blank_or_too_many_lines(self):
        self.assertEqual(self.create(speakers=["  Speaker: A  "]).data["speakers"], ["Speaker: A"])
        self.assertIn("collaborators", self.create(slug="b", collaborators=["A", "  "]).data)
        self.assertIn("focus_areas", self.create(slug="c", focus_areas=[f"Area {i}" for i in range(31)]).data)

    def test_unknown_mode_is_refused(self):
        self.assertIn("mode", self.create(mode="virtual").data)


def png(name="p.png"):
    return SimpleUploadedFile(name, b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class EventGalleryTests(APITestCase):
    def setUp(self):
        self.editor = User.objects.create_user(username="editor3", password="pw12345", role="editor")
        self.researcher = User.objects.create_user(username="res3", password="pw12345", role="researcher")
        self.event = Event.objects.create(
            slug="gallery",
            title="Gallery",
            start_date="2026-10-01",
            status="published",
            published_at=timezone.now(),
            created_by=self.editor,
        )

    def add(self, **extra):
        return self.client.post("/api/v1/events/gallery/images/", {"image": png(), **extra}, format="multipart")

    def test_editor_adds_and_removes_photos_and_the_public_sees_them_in_order(self):
        self.client.force_authenticate(self.editor)
        first = self.add(caption="Opening session")
        self.assertEqual(first.status_code, 201, first.data)
        self.add()
        self.client.force_authenticate(None)
        images = self.client.get("/api/v1/events/gallery/").data["images"]
        self.assertEqual([i["caption"] for i in images], ["Opening session", ""])
        self.assertIn("/events/gallery/", images[0]["image"])

        self.client.force_authenticate(self.editor)
        self.assertEqual(self.client.delete(f"/api/v1/events/gallery/images/{first.data['id']}/").status_code, 204)
        self.assertEqual(len(self.client.get("/api/v1/events/gallery/").data["images"]), 1)
        self.assertEqual(self.client.delete("/api/v1/events/gallery/images/99999/").status_code, 404)

    def test_researcher_cannot_change_a_published_event_and_anonymous_cannot_at_all(self):
        self.assertEqual(self.add().status_code, 401)
        self.client.force_authenticate(self.researcher)
        self.assertEqual(self.add().status_code, 403)

    def test_researcher_may_add_photos_to_their_own_draft(self):
        Event.objects.create(slug="mine", title="Mine", start_date="2026-10-01", created_by=self.researcher)
        self.client.force_authenticate(self.researcher)
        response = self.client.post("/api/v1/events/mine/images/", {"image": png()}, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)

    def test_photo_type_and_count_are_limited(self):
        self.client.force_authenticate(self.editor)
        gif = SimpleUploadedFile("x.gif", b"GIF89a", "image/gif")
        self.assertEqual(
            self.client.post("/api/v1/events/gallery/images/", {"image": gif}, format="multipart").status_code, 400
        )
        for _ in range(EventImage.MAX_PER_EVENT):
            EventImage.objects.create(event=self.event, image="events/gallery/x.png")
        response = self.add()
        self.assertEqual(response.status_code, 400)
        self.assertIn("up to 20", response.data["detail"])


class OctoberEventsMigrationTests(TestCase):
    def load(self):
        from django.apps import apps

        importlib.import_module("apps.events.migrations.0003_october_events").load_events(apps, None)

    def test_updates_existing_rows_in_place_keeps_images_and_adds_the_rest_once(self):
        admin = User.objects.create_user(username="admin9", password="pw12345", role="admin")
        staff = User.objects.create_user(username="staff9", password="pw12345", role="editor")
        Event.objects.create(
            slug="political-data-intelligence-in-the-digit",
            title="â€œGarbled",
            start_date="2025-04-12",
            summary="Speaker: ...",
            image="events/Expert_1.png",
            status="published",
            created_by=staff,
        )
        self.load()
        self.load()
        self.assertEqual(Event.objects.count(), 4)
        fixed = Event.objects.get(slug="political-data-intelligence-in-the-digit")
        self.assertEqual(str(fixed.start_date), "2025-12-04")
        self.assertEqual(fixed.title, "Political Data Intelligence in the Digital Age")
        self.assertEqual((fixed.image.name, fixed.created_by, fixed.mode), ("events/Expert_1.png", staff, "online"))
        conclave = Event.objects.get(slug="kerala-demographic-conclave-2026")
        self.assertEqual((conclave.status, conclave.created_by), ("published", admin))
        self.assertTrue(conclave.date_note.startswith("December 2026"))

    def test_creates_nothing_without_users(self):
        self.load()
        self.assertEqual(Event.objects.count(), 0)


class MergeHandEnteredDuplicatesTests(TestCase):
    def merge(self):
        from django.apps import apps

        importlib.import_module("apps.events.migrations.0004_merge_hand_entered_duplicates").merge(apps, None)

    def setUp(self):
        self.owner = User.objects.create_user(username="owner9", password="pw12345", role="admin")

    def event(self, slug, **fields):
        return Event.objects.create(slug=slug, created_by=self.owner, status="published", **fields)

    def test_details_move_onto_the_hand_entered_row_and_the_copy_is_deleted(self):
        kept = self.event(
            "kerala-demographic-conclave-navigating-p",
            title="Kerala Demographic Conclave",
            start_date="2026-12-24",
            summary="Collaborators: ...\r\nFocus Areas: ...",
            location="Thiruvananthapuram",
            image="events/conclave.png",
        )
        copy = self.event(
            "kerala-demographic-conclave-2026",
            title="Kerala Demographic Conclave: Navigating Population Transition and Policy Realities",
            start_date="2026-12-14",
            summary="A one-day conclave.",
            location="Thiruvananthapuram",
            mode="hybrid",
            start_time="09:30",
            date_note="December 2026 (3rd or 4th week)",
            speakers=["Key participants: Demographers"],
            focus_areas=["Demographic transition: Fertility declines"],
        )
        EventImage.objects.create(event=copy, image="events/gallery/a.png")
        self.merge()

        kept.refresh_from_db()
        self.assertFalse(Event.objects.filter(slug="kerala-demographic-conclave-2026").exists())
        self.assertEqual(kept.summary, "A one-day conclave.")
        self.assertEqual((kept.mode, kept.date_note), ("hybrid", "December 2026 (3rd or 4th week)"))
        self.assertEqual(kept.focus_areas, ["Demographic transition: Fertility declines"])
        # The owner's own choices stay: start date, photo, slug.
        self.assertEqual((str(kept.start_date), kept.image.name), ("2026-12-24", "events/conclave.png"))
        self.assertEqual(kept.images.count(), 1)

    def test_does_nothing_without_the_hand_entered_row(self):
        self.event("legislative-leadership-forum-2026", title="Forum", start_date="2026-10-03", mode="in_person")
        self.merge()
        self.merge()
        self.assertEqual(list(Event.objects.values_list("slug", flat=True)), ["legislative-leadership-forum-2026"])


ANDROTH_SLUG = "political-data-intelligence-in-the-digit"
SIR_SLUG = "sir-update-today-decide-tomorrow-2025"


class RestoreEventDetailsTests(TestCase):
    def restore(self):
        from django.apps import apps

        importlib.import_module("apps.events.migrations.0005_restore_event_details").restore(apps, None)

    def setUp(self):
        self.owner = User.objects.create_user(username="owner8", password="pw12345", role="admin")

    def event(self, slug, **fields):
        return Event.objects.create(slug=slug, created_by=self.owner, status="published", **fields)

    def test_fills_empty_details_and_keeps_the_owners_date_and_photo(self):
        forum = self.event(
            "legislative-leadership-forum-good-govern",
            title="Legislative Leadership Forum",
            start_date="2026-10-03",
            summary="Collaborators: IUML\r\nFocus Areas: ...",
            location="Vazhayur",
            image="events/league_event.jpeg",
        )
        self.restore()
        forum.refresh_from_db()
        self.assertEqual((forum.mode, forum.location), ("in_person", "SAFI College, Vazhayur"))
        self.assertEqual(len(forum.speakers), 5)
        self.assertFalse(forum.summary.startswith("Collaborators"))
        self.assertEqual((str(forum.start_date), forum.image.name), ("2026-10-03", "events/league_event.jpeg"))

    def test_leaves_events_staff_have_since_filled_in(self):
        conclave = self.event(
            "kerala-demographic-conclave-navigating-p",
            title="Conclave",
            start_date="2026-12-24",
            summary="Staff's own summary.",
            mode="hybrid",
        )
        androth = self.event(ANDROTH_SLUG, title="Lecture", start_date="2025-12-05", summary="A lecture.")
        self.restore()
        conclave.refresh_from_db()
        androth.refresh_from_db()
        self.assertEqual((conclave.summary, conclave.speakers), ("Staff's own summary.", []))
        self.assertEqual((androth.summary, str(androth.start_date)), ("A lecture.", "2025-12-05"))

    def test_restores_the_androth_summary_and_date_and_the_sir_title(self):
        androth = self.event(
            ANDROTH_SLUG, title="Lecture", start_date="2025-04-12", summary="Speaker: Muhammed Thufail"
        )
        sir = self.event(SIR_SLUG, title="SIR: “Update Today, Decide Tomorrow�", start_date="2025-11-02")
        self.restore()
        self.restore()
        androth.refresh_from_db()
        sir.refresh_from_db()
        self.assertEqual(str(androth.start_date), "2025-12-04")
        self.assertTrue(androth.summary.startswith("An online lecture"))
        self.assertEqual(sir.title, "SIR: “Update Today, Decide Tomorrow”")

    def test_does_nothing_on_a_fresh_database(self):
        self.restore()
        self.assertEqual(Event.objects.count(), 0)
