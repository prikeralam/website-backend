from django.utils import timezone
from rest_framework.test import APITestCase

from apps.workflow.models import WorkflowStatus

from .models import ContentBlock, Document, PersonProfile, Testimonial


def make_user(django_user_model, role, username):
    return django_user_model.objects.create_user(username=username, password="pw12345", role=role)


class ContentBlockSlugLookupTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = make_user(get_user_model(), "researcher", "researcher1")
        self.client.force_authenticate(self.user)
        self.block = ContentBlock.objects.create(
            slug="hero-copy", title="Hero", body="Body text", created_by=self.user
        )

    def test_retrieve_by_slug(self):
        response = self.client.get(f"/api/v1/content-blocks/{self.block.slug}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["slug"], "hero-copy")

    def test_seo_defaults_applied_on_save(self):
        self.assertEqual(self.block.seo_title, "Hero")
        self.assertTrue(self.block.seo_description)


class PersonProfileDocumentFilterTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = make_user(get_user_model(), "editor", "editor1")
        self.client.force_authenticate(self.user)
        PersonProfile.objects.create(
            slug="jane", name="Jane", role_title="Director", group="executive", created_by=self.user
        )
        PersonProfile.objects.create(
            slug="john", name="John", role_title="Fellow", group="fellow", created_by=self.user
        )
        Document.objects.create(
            slug="annual-report-2025",
            title="Annual Report 2025",
            file="documents/ar2025.pdf",
            document_type="Annual Report",
            year=2025,
            created_by=self.user,
        )
        Document.objects.create(
            slug="strategic-plan",
            title="Strategic Plan",
            file="documents/plan.pdf",
            document_type="Strategic Plan",
            year=2024,
            created_by=self.user,
        )

    def test_person_profile_filter_by_group(self):
        response = self.client.get("/api/v1/people/?group=executive")
        self.assertEqual(response.status_code, 200)
        results = response.data["results"] if "results" in response.data else response.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["slug"], "jane")

    def test_document_filter_by_type_and_year(self):
        response = self.client.get("/api/v1/documents/?document_type=Annual Report&year=2025")
        self.assertEqual(response.status_code, 200)
        results = response.data["results"] if "results" in response.data else response.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["slug"], "annual-report-2025")


class LatestUpdatesViewTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = make_user(get_user_model(), "editor", "editor2")
        self.client.force_authenticate(self.user)
        older = ContentBlock.objects.create(slug="older", title="Older", body="x", created_by=self.user)
        older.status = WorkflowStatus.PUBLISHED
        older.published_at = timezone.now() - timezone.timedelta(days=2)
        older.save()

        newer = Testimonial.objects.create(
            slug="newer", quote="Great work", attribution="A Donor", created_by=self.user
        )
        newer.status = WorkflowStatus.PUBLISHED
        newer.published_at = timezone.now()
        newer.save()

        ContentBlock.objects.create(slug="still-draft", title="Draft", body="x", created_by=self.user)

    def test_returns_only_published_ordered_newest_first(self):
        response = self.client.get("/api/v1/updates/latest/")
        self.assertEqual(response.status_code, 200)
        slugs = [item["slug"] for item in response.data]
        self.assertEqual(slugs, ["newer", "older"])

    def test_types_filter(self):
        response = self.client.get("/api/v1/updates/latest/?types=testimonial")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["slug"] for item in response.data], ["newer"])


class WorkflowTransitionPermissionTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.researcher = make_user(User, "researcher", "researcher2")
        self.editor = make_user(User, "editor", "editor3")
        self.block = ContentBlock.objects.create(
            slug="draft-block", title="Draft", body="x", created_by=self.researcher
        )

    def test_own_contributor_can_submit_for_review(self):
        self.client.force_authenticate(self.researcher)
        response = self.client.post(
            f"/api/v1/content-blocks/{self.block.slug}/transition/", {"status": "in_review"}
        )
        self.assertEqual(response.status_code, 200)
        self.block.refresh_from_db()
        self.assertEqual(self.block.status, "in_review")

    def test_researcher_cannot_approve(self):
        self.block.status = "in_review"
        self.block.save(update_fields=["status"])
        self.client.force_authenticate(self.researcher)
        response = self.client.post(
            f"/api/v1/content-blocks/{self.block.slug}/transition/", {"status": "approved"}
        )
        self.assertEqual(response.status_code, 403)

    def test_editor_can_approve(self):
        self.block.status = "in_review"
        self.block.save(update_fields=["status"])
        self.client.force_authenticate(self.editor)
        response = self.client.post(
            f"/api/v1/content-blocks/{self.block.slug}/transition/", {"status": "approved"}
        )
        self.assertEqual(response.status_code, 200)
