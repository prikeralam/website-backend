import tempfile
from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.publications.models import Publication
from apps.taxonomy.models import Theme

from .models import Mention, Recognition

User = get_user_model()
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def mention_data(**extra):
    return {
        "slug": "hindu-plus-one",
        "title": "Plus One seat shortage in Malappuram",
        "publisher": "The Hindu",
        "url": "https://www.thehindu.com/example",
        "kind": "news",
        "date": "2026-09-01",
        **extra,
    }


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class MentionTests(APITestCase):
    def setUp(self):
        self.editor = User.objects.create_user(username="editor", password="pw12345", role="editor")
        self.researcher = User.objects.create_user(username="researcher", password="pw12345", role="researcher")

    def test_contributor_drafts_and_only_published_mentions_are_public(self):
        self.client.force_authenticate(self.researcher)
        created = self.client.post("/api/v1/mentions/", mention_data(), format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["status"], "draft")

        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/v1/mentions/").data["count"], 0)

        self.client.force_authenticate(self.editor)
        for status in ("in_review", "approved", "published"):
            self.client.post("/api/v1/mentions/hindu-plus-one/transition/", {"status": status}, format="json")
        self.client.force_authenticate(None)
        public = self.client.get("/api/v1/mentions/").data["results"]
        self.assertEqual([m["slug"] for m in public], ["hindu-plus-one"])

    def test_links_must_be_https(self):
        self.client.force_authenticate(self.editor)
        response = self.client.post("/api/v1/mentions/", mention_data(url="http://example.org/a"), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("url", response.data)

    def test_links_the_cited_publication_by_slug_and_filters_by_kind(self):
        health = Theme.objects.get(slug="health")
        sub = Theme.objects.create(slug="phc", name="PHC", parent=health)
        Publication.objects.create(
            slug="healthcare-gap", title="Healthcare gap", abstract="A", format="report", sub_theme=sub,
            date=date(2026, 1, 1), created_by=self.editor,
        )
        self.client.force_authenticate(self.editor)
        response = self.client.post("/api/v1/mentions/", mention_data(publication="healthcare-gap"), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["publication"], "healthcare-gap")
        self.client.post("/api/v1/mentions/", mention_data(slug="paper", kind="research"), format="json")
        Mention.objects.update(status="published")

        self.client.force_authenticate(None)
        research = self.client.get("/api/v1/mentions/?kind=research").data["results"]
        self.assertEqual([m["slug"] for m in research], ["paper"])

    def test_newest_first_and_logo_upload(self):
        self.client.force_authenticate(self.editor)
        logo = SimpleUploadedFile("hindu.png", PNG, content_type="image/png")
        data = {**mention_data(slug="old", date="2025-01-01"), "publisher_logo": logo}
        created = self.client.post("/api/v1/mentions/", data, format="multipart")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertTrue(created.data["publisher_logo"].endswith(".png"))
        self.client.post("/api/v1/mentions/", mention_data(slug="new", date="2026-05-01"), format="json")
        Mention.objects.update(status="published")
        self.assertEqual([m["slug"] for m in self.client.get("/api/v1/mentions/").data["results"]], ["new", "old"])


class RecognitionTests(APITestCase):
    def test_editor_creates_and_public_sees_published_newest_first(self):
        editor = User.objects.create_user(username="editor", password="pw12345", role="editor")
        self.client.force_authenticate(editor)
        for slug, year in (("grant-2024", 2024), ("award-2026", 2026)):
            data = {"slug": slug, "title": slug, "awarded_by": "A body", "year": year}
            response = self.client.post("/api/v1/recognition/", data, format="json")
            self.assertEqual(response.status_code, 201, response.data)
        Recognition.objects.update(status="published")
        self.client.force_authenticate(None)
        listed = self.client.get("/api/v1/recognition/").data["results"]
        self.assertEqual([r["slug"] for r in listed], ["award-2026", "grant-2024"])


class RecognitionLinkTests(APITestCase):
    def test_recognition_links_must_be_https_too(self):
        editor = User.objects.create_user(username="editor", password="pw12345", role="editor")
        self.client.force_authenticate(editor)
        data = {"slug": "g", "title": "G", "awarded_by": "B", "year": 2026, "url": "http://example.org"}
        response = self.client.post("/api/v1/recognition/", data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("url", response.data)
