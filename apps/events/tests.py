from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Event

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
