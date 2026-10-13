"""Public-read boundaries (issue #15): what an anonymous visitor, a signed-in `public` user,
a contributor and staff can each see, and what stays closed to anonymous callers.

The rule under test is docs/api/README.md's permission matrix: published objects are readable
by everyone; drafts are visible only to their creator (contributors) and to editor/admin.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.careers.models import JobOpening
from apps.content.models import ContentBlock, Document, PersonProfile, Testimonial
from apps.datarepo.models import Dashboard, Dataset
from apps.events.models import Event
from apps.projects.models import Project
from apps.publications.models import Publication
from apps.taxonomy.models import Theme

User = get_user_model()

PUBLIC_READ_ENDPOINTS = [
    "/api/v1/content-blocks/",
    "/api/v1/testimonials/",
    "/api/v1/people/",
    "/api/v1/documents/",
    "/api/v1/projects/",
    "/api/v1/publications/",
    "/api/v1/datasets/",
    "/api/v1/dashboards/",
    "/api/v1/themes/",
    "/api/v1/updates/latest/",
    "/api/v1/jobs/",
    "/api/v1/events/",
]


def slugs(response):
    body = response.json()
    results = body["results"] if isinstance(body, dict) else body
    return {item["slug"] for item in results}


class PublicReadTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(username="author", password="pw12345", role="researcher")
        cls.other_researcher = User.objects.create_user(username="other", password="pw12345", role="researcher")
        cls.visitor = User.objects.create_user(username="visitor", password="pw12345", role="public")
        cls.editor = User.objects.create_user(username="editor", password="pw12345", role="editor")
        cls.top_theme = Theme.objects.get(slug="education")
        cls.sub_theme = Theme.objects.create(slug="primary-ed", name="Primary", parent=cls.top_theme)

    def make(self, model, slug, status, **fields):
        published_at = timezone.now() if status == "published" else None
        return model.objects.create(
            slug=slug, status=status, published_at=published_at, created_by=self.author, **fields
        )


class AnonymousReadTests(PublicReadTestCase):
    def test_public_read_endpoints_are_open_to_anonymous_visitors(self):
        for url in PUBLIC_READ_ENDPOINTS:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_account_and_review_endpoints_stay_closed_to_anonymous_visitors(self):
        closed = ["/api/v1/users/me/role/", "/api/v1/audit-log/", "/api/v1/access-requests/", "/api/v1/applications/"]
        for url in closed:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401)

    def test_anonymous_visitors_cannot_write(self):
        block = self.make(ContentBlock, "about", "published", title="About", body="x")
        for method, url, data in [
            ("post", "/api/v1/content-blocks/", {"slug": "new", "title": "t", "body": "b"}),
            ("patch", f"/api/v1/content-blocks/{block.slug}/", {"title": "hacked"}),
            ("delete", f"/api/v1/content-blocks/{block.slug}/", None),
            ("post", f"/api/v1/content-blocks/{block.slug}/transition/", {"status": "unpublished"}),
            ("post", "/api/v1/themes/", {"slug": "x", "name": "x"}),
            ("post", "/api/v1/datasets/any/request-access/", None),
        ]:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, data, format="json")
                self.assertIn(response.status_code, (401, 403))
        block.refresh_from_db()
        self.assertEqual(block.title, "About")

    def test_only_published_content_is_listed_and_retrievable(self):
        self.make(ContentBlock, "live", "published", title="Live", body="x")
        for status in ["draft", "in_review", "approved", "unpublished"]:
            self.make(ContentBlock, f"hidden-{status}", status, title=status, body="x")

        self.assertEqual(slugs(self.client.get("/api/v1/content-blocks/")), {"live"})
        self.assertEqual(self.client.get("/api/v1/content-blocks/live/").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/content-blocks/hidden-draft/").status_code, 404)

    def test_every_workflowed_content_type_hides_drafts(self):
        cases = [
            (Testimonial, "testimonials", {"quote": "q", "attribution": "a"}),
            (PersonProfile, "people", {"name": "n", "role_title": "r", "group": "team"}),
            (
                Document,
                "documents",
                {"title": "t", "file": SimpleUploadedFile("d.pdf", b"%PDF")},
            ),
            (Project, "projects", {"title": "t", "blurb": "b"}),
            (JobOpening, "jobs", {"title": "t"}),
            (Event, "events", {"title": "t", "start_date": "2026-11-01"}),
        ]
        for model, route, fields in cases:
            with self.subTest(route=route):
                self.make(model, f"{route}-live", "published", **fields)
                if "file" in fields:
                    fields = {**fields, "file": SimpleUploadedFile("e.pdf", b"%PDF")}
                self.make(model, f"{route}-draft", "draft", **fields)
                self.assertEqual(slugs(self.client.get(f"/api/v1/{route}/")), {f"{route}-live"})

    def test_latest_updates_feed_lists_published_items_only(self):
        self.make(ContentBlock, "live", "published", title="Live", body="x")
        self.make(ContentBlock, "draft", "draft", title="Draft", body="x")
        response = self.client.get("/api/v1/updates/latest/")
        self.assertEqual({item["slug"] for item in response.json()}, {"live"})


class RoleVisibilityTests(PublicReadTestCase):
    def setUp(self):
        self.make(ContentBlock, "live", "published", title="Live", body="x")
        self.make(ContentBlock, "own-draft", "draft", title="Mine", body="x")
        ContentBlock.objects.create(
            slug="other-draft", title="Theirs", body="x", status="draft", created_by=self.other_researcher
        )

    def listed_by(self, user):
        self.client.force_authenticate(user)
        return slugs(self.client.get("/api/v1/content-blocks/"))

    def test_signed_in_public_role_sees_published_only(self):
        self.assertEqual(self.listed_by(self.visitor), {"live"})

    def test_contributor_sees_published_and_own_drafts_only(self):
        self.assertEqual(self.listed_by(self.author), {"live", "own-draft"})

    def test_editor_sees_everything(self):
        self.assertEqual(self.listed_by(self.editor), {"live", "own-draft", "other-draft"})

    def test_contributor_cannot_open_another_contributors_draft(self):
        self.client.force_authenticate(self.author)
        self.assertEqual(self.client.get("/api/v1/content-blocks/other-draft/").status_code, 404)


class PublicationLeakTests(PublicReadTestCase):
    def setUp(self):
        base = {"abstract": "x", "format": "report", "sub_theme": self.sub_theme, "date": date(2025, 1, 1)}
        self.make(Publication, "open", "published", title="Open", visibility="public", **base)
        self.make(Publication, "members-only", "published", title="Private", visibility="private", **base)
        self.make(Publication, "unfinished", "draft", title="Draft", visibility="public", **base)

    def test_anonymous_sees_only_published_public_publications(self):
        self.assertEqual(slugs(self.client.get("/api/v1/publications/")), {"open"})

    def test_anonymous_cannot_reach_private_or_draft_publications_by_slug(self):
        for slug in ["members-only", "unfinished"]:
            with self.subTest(slug=slug):
                self.assertEqual(self.client.get(f"/api/v1/publications/{slug}/").status_code, 404)
                self.assertEqual(self.client.get(f"/api/v1/publications/{slug}/citation/").status_code, 404)
                self.assertEqual(self.client.get(f"/api/v1/publications/{slug}/download/").status_code, 404)

    def test_anonymous_can_cite_a_public_publication(self):
        self.assertEqual(self.client.get("/api/v1/publications/open/citation/?format=apa").status_code, 200)

    def test_staff_still_sees_private_publications(self):
        self.client.force_authenticate(self.editor)
        self.assertIn("members-only", slugs(self.client.get("/api/v1/publications/")))


class DatasetLeakTests(PublicReadTestCase):
    def setUp(self):
        def dataset(slug, visibility, status="published"):
            return self.make(
                Dataset,
                slug,
                status,
                title=slug,
                file=SimpleUploadedFile(f"{slug}.csv", b"a,b\n1,2\n"),
                format="csv",
                sub_theme=self.sub_theme,
                visibility=visibility,
            )

        dataset("open-ds", "public")
        dataset("gated-ds", "on_request")
        dataset("internal-ds", "internal_only")
        dataset("draft-ds", "public", status="draft")

    def test_anonymous_sees_published_public_and_on_request_datasets_only(self):
        self.assertEqual(slugs(self.client.get("/api/v1/datasets/")), {"open-ds", "gated-ds"})

    def test_internal_only_and_draft_datasets_are_unreachable_anonymously(self):
        for slug in ["internal-ds", "draft-ds"]:
            with self.subTest(slug=slug):
                for suffix in ["", "download/", "preview/table/"]:
                    self.assertEqual(self.client.get(f"/api/v1/datasets/{slug}/{suffix}").status_code, 404)

    def test_file_url_is_never_exposed_anonymously(self):
        # Every download needs a signed-in account with a confirmed email, public datasets included.
        by_slug = {item["slug"]: item for item in self.client.get("/api/v1/datasets/").json()["results"]}
        self.assertNotIn("file", by_slug["open-ds"])
        self.assertNotIn("file", by_slug["gated-ds"])
        self.assertNotIn("file", self.client.get("/api/v1/datasets/gated-ds/").json())

    def test_public_file_url_needs_a_confirmed_email(self):
        self.client.force_authenticate(self.visitor)
        self.assertNotIn("file", self.client.get("/api/v1/datasets/open-ds/").json())
        self.visitor.email_verified = True
        self.visitor.save(update_fields=["email_verified"])
        self.assertIn("file", self.client.get("/api/v1/datasets/open-ds/").json())

    def test_on_request_file_url_stays_hidden_from_signed_in_users_without_approval(self):
        self.client.force_authenticate(self.visitor)
        self.assertNotIn("file", self.client.get("/api/v1/datasets/gated-ds/").json())

    def test_anonymous_can_download_nothing(self):
        self.assertEqual(self.client.get("/api/v1/datasets/open-ds/download/").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/datasets/gated-ds/download/").status_code, 403)

    def test_anonymous_can_preview_a_public_dataset(self):
        self.assertEqual(self.client.get("/api/v1/datasets/open-ds/preview/table/").status_code, 200)


class DashboardLeakTests(PublicReadTestCase):
    def test_anonymous_sees_published_dashboards_only(self):
        fields = {"title": "d", "embed_url": "https://example.org/e", "embed_type": "d3", "theme": self.top_theme}
        self.make(Dashboard, "live-dash", "published", **fields)
        self.make(Dashboard, "draft-dash", "draft", **fields)
        self.assertEqual(slugs(self.client.get("/api/v1/dashboards/")), {"live-dash"})
