import tempfile
from importlib import import_module

from django.apps import apps
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
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


class PersonPhotoMigrationTests(TestCase):
    migration = import_module("apps.content.migrations.0004_person_photos_on_frontend")

    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = make_user(get_user_model(), "editor", "editor1")

    def person(self, slug, photo_url):
        return PersonProfile.objects.create(
            slug=slug, name=slug, role_title="Role", group="team", photo_url=photo_url, created_by=self.user
        )

    @override_settings(FRONTEND_URL="https://staging.example.org")
    def test_moves_prototype_photos_to_the_frontend_and_leaves_others_alone(self):
        prototype = self.person("a", "https://pri-website-pink.vercel.app/people/team/noushad.jpg")
        elsewhere = self.person("b", "https://cdn.example.com/people/team/b.jpg")
        empty = self.person("c", "")

        self.migration.rewrite_photo_urls(apps, None)

        for obj in (prototype, elsewhere, empty):
            obj.refresh_from_db()
        self.assertEqual(prototype.photo_url, "https://staging.example.org/people/team/noushad.jpg")
        self.assertEqual(elsewhere.photo_url, "https://cdn.example.com/people/team/b.jpg")
        self.assertEqual(empty.photo_url, "")


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ImageUploadTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.editor = make_user(get_user_model(), "editor", "editor1")
        self.client.force_authenticate(self.editor)

    def create_person(self, **extra):
        data = {"slug": "asha", "name": "Asha", "role_title": "Analyst", "group": "team", **extra}
        return self.client.post("/api/v1/people/", data, format="multipart")

    def test_uploaded_photo_is_returned_as_a_url(self):
        response = self.create_person(photo=SimpleUploadedFile("asha.png", PNG, content_type="image/png"))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertRegex(response.data["photo"], r"/people/asha[^/]*\.png$")
        self.assertEqual(response.data["photo_url"], "")

    def test_rejects_files_that_are_not_images(self):
        response = self.create_person(photo=SimpleUploadedFile("cv.pdf", b"%PDF-1.4", content_type="application/pdf"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("photo", response.data)

    def test_rejects_images_over_5_mb(self):
        big = SimpleUploadedFile("big.jpg", b"\xff" * (5 * 1024 * 1024 + 1), content_type="image/jpeg")
        response = self.create_person(photo=big)
        self.assertEqual(response.status_code, 400)
        self.assertIn("photo", response.data)

    def test_null_or_empty_removes_the_upload(self):
        created = self.create_person(photo=SimpleUploadedFile("asha.png", PNG, content_type="image/png")).data
        cleared = self.client.patch(f"/api/v1/people/{created['id']}/", {"photo": None}, format="json")
        self.assertEqual(cleared.status_code, 200, cleared.data)
        self.assertIsNone(cleared.data["photo"])

        self.client.patch(
            f"/api/v1/people/{created['id']}/",
            {"photo": SimpleUploadedFile("again.png", PNG, content_type="image/png")},
            format="multipart",
        )
        cleared = self.client.patch(f"/api/v1/people/{created['id']}/", {"photo": ""}, format="multipart")
        self.assertEqual(cleared.status_code, 200, cleared.data)
        self.assertIsNone(cleared.data["photo"])

    def test_editing_other_fields_keeps_the_upload(self):
        created = self.create_person(photo=SimpleUploadedFile("asha.png", PNG, content_type="image/png")).data
        updated = self.client.patch(f"/api/v1/people/{created['id']}/", {"bio": "New bio"}, format="json")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["photo"], created["photo"])

    def test_projects_take_an_uploaded_image(self):
        image = SimpleUploadedFile("p.webp", b"RIFF", content_type="image/webp")
        data = {"slug": "p", "title": "P", "blurb": "B", "image": image}
        response = self.client.post("/api/v1/projects/", data, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["image"].endswith(".webp"))


class PersonContactLinkTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.editor = make_user(get_user_model(), "editor", "editor1")
        self.client.force_authenticate(self.editor)

    def create(self, **extra):
        data = {"slug": "asha", "name": "Asha", "role_title": "Analyst", "group": "team", **extra}
        return self.client.post("/api/v1/people/", data, format="json")

    def test_saves_and_publishes_linkedin_and_email(self):
        response = self.create(linkedin_url="https://www.linkedin.com/in/asha", email="asha@priresearch.in")
        self.assertEqual(response.status_code, 201, response.data)

        person = PersonProfile.objects.get(slug="asha")
        person.status = WorkflowStatus.PUBLISHED
        person.published_at = timezone.now()
        person.save()
        self.client.force_authenticate(None)
        public = self.client.get("/api/v1/people/?group=team").data["results"][0]
        self.assertEqual(public["linkedin_url"], "https://www.linkedin.com/in/asha")
        self.assertEqual(public["email"], "asha@priresearch.in")

    def test_both_are_optional(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual((response.data["linkedin_url"], response.data["email"]), ("", ""))

    def test_linkedin_link_must_be_https_on_linkedin(self):
        for url in ["http://www.linkedin.com/in/asha", "https://evil.example/linkedin.com", "https://linkedin.com.evil.example/in/a"]:
            with self.subTest(url=url):
                response = self.create(slug=f"p-{abs(hash(url)) % 10000}", linkedin_url=url)
                self.assertEqual(response.status_code, 400)
                self.assertIn("linkedin_url", response.data)

    def test_rejects_an_invalid_email(self):
        response = self.create(email="not-an-email")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)


class PersonOrderAndWebsiteTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.editor = make_user(get_user_model(), "editor", "editor1")
        self.client.force_authenticate(self.editor)

    def create(self, slug, **extra):
        data = {"slug": slug, "name": slug.title(), "role_title": "Partner institution", "group": "partner", **extra}
        return self.client.post("/api/v1/people/", data, format="json")

    def test_lists_sort_by_display_order_then_oldest_first(self):
        for slug, order in [("c", 2), ("a", 0), ("b", 1), ("d", 0)]:
            self.assertEqual(self.create(slug, display_order=order).status_code, 201)
        PersonProfile.objects.update(status=WorkflowStatus.PUBLISHED, published_at=timezone.now())
        self.client.force_authenticate(None)
        results = self.client.get("/api/v1/people/?group=partner").data["results"]
        self.assertEqual([p["slug"] for p in results], ["a", "d", "b", "c"])

    def test_display_order_defaults_to_zero(self):
        self.assertEqual(self.create("a").data["display_order"], 0)

    def test_saves_an_https_website(self):
        response = self.create("a", website_url="https://safi.ac.in")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["website_url"], "https://safi.ac.in")

    def test_website_must_be_https(self):
        response = self.create("a", website_url="http://safi.ac.in")
        self.assertEqual(response.status_code, 400)
        self.assertIn("website_url", response.data)
