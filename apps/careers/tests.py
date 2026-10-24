import tempfile
from importlib import import_module
from unittest import mock

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import AuditLog

from .models import Application, JobOpening

User = get_user_model()

PDF = b"%PDF-1.4\n%%EOF\n"
DOCX = b"PK\x03\x04" + b"\x00" * 26


def pdf(name="cv.pdf", content=PDF):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), CONTACT_EMAIL="contact@priresearch.in")
class ApplicationSubmissionTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(username="admin1", password="pw12345", role="admin")
        self.job = JobOpening.objects.create(
            slug="analyst", title="Analyst", status="published", published_at=timezone.now(), created_by=self.owner
        )

    def apply(self, **extra):
        data = {
            "kind": "fellowship",
            "full_name": " Asha K ",
            "email": "asha@example.org",
            "cv": pdf(),
            "cover_letter": SimpleUploadedFile("letter.docx", DOCX),
            **extra,
        }
        return self.client.post("/api/v1/apply/", data, format="multipart")

    def test_stores_the_application_and_emails_pri_without_the_files(self):
        response = self.apply()
        self.assertEqual(response.status_code, 201, response.data)
        stored = Application.objects.get()
        self.assertEqual((stored.kind, stored.full_name, stored.status), ("fellowship", "Asha K", "new"))
        self.assertRegex(stored.cv.name, r"^applications/[0-9a-f]{32}\.pdf$")
        self.assertRegex(stored.cover_letter.name, r"^applications/[0-9a-f]{32}\.docx$")
        self.assertFalse(stored.writing_sample)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["contact@priresearch.in"])
        self.assertEqual(mail.outbox[0].reply_to, ["asha@example.org"])
        self.assertEqual(mail.outbox[0].attachments, [])

    def test_a_job_application_names_a_published_opening(self):
        self.assertEqual(self.apply(kind="job", job="analyst").status_code, 201)
        self.assertEqual(Application.objects.get().job, self.job)
        self.assertIn("Analyst", mail.outbox[0].subject)

    def test_a_job_application_needs_a_job(self):
        response = self.apply(kind="job")
        self.assertEqual(response.status_code, 400)
        self.assertIn("job", response.data)

    def test_draft_openings_cannot_be_applied_for(self):
        JobOpening.objects.create(slug="secret", title="Secret", status="draft", created_by=self.owner)
        response = self.apply(kind="job", job="secret")
        self.assertEqual(response.status_code, 400)
        self.assertIn("job", response.data)

    def test_the_job_is_dropped_for_fellowships(self):
        self.assertEqual(self.apply(job="analyst").status_code, 201)
        self.assertIsNone(Application.objects.get().job)

    def test_cv_and_cover_letter_are_required(self):
        response = self.client.post(
            "/api/v1/apply/",
            {"kind": "internship", "full_name": "A", "email": "a@example.org", "cv": pdf()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("cover_letter", response.data)

    def test_a_writing_sample_is_optional_unless_the_role_requires_it(self):
        self.assertEqual(self.apply(kind="job", job="analyst").status_code, 201)
        JobOpening.objects.create(slug="research-assistant", title="Research Assistant", status="published",
                                  writing_sample="required", created_by=self.owner)
        response = self.apply(kind="job", job="research-assistant", email="b@example.org")
        self.assertEqual(response.status_code, 400)
        self.assertIn("asks for a writing sample", str(response.data["writing_sample"]))
        response = self.apply(kind="job", job="research-assistant", email="b@example.org",
                              writing_sample=pdf("essay.pdf"))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertRegex(Application.objects.get(job__slug="research-assistant").writing_sample.name,
                         r"^applications/[0-9a-f]{32}\.pdf$")
        self.assertIn("writing sample", mail.outbox[-1].body)

    def test_fellowships_may_send_a_writing_sample_checked_like_the_others(self):
        self.assertEqual(self.apply(writing_sample=pdf("essay.pdf")).status_code, 201)
        response = self.apply(email="c@example.org", writing_sample=SimpleUploadedFile("essay.exe", b"MZ"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("writing_sample", response.data)

    def test_rejects_other_file_types(self):
        response = self.apply(cv=SimpleUploadedFile("cv.exe", b"MZ\x90\x00"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("cv", response.data)

    def test_rejects_a_renamed_file(self):
        response = self.apply(cv=pdf(content=b"MZ\x90\x00 not a pdf"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("cv", response.data)

    def test_rejects_files_over_5_mb(self):
        response = self.apply(cover_letter=pdf("letter.pdf", PDF + b"0" * (5 * 1024 * 1024)))
        self.assertEqual(response.status_code, 400)
        self.assertIn("cover_letter", response.data)

    def test_honeypot_answers_success_and_keeps_nothing(self):
        self.assertEqual(self.apply(website="spam.example").status_code, 201)
        self.assertFalse(Application.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_a_mail_failure_still_keeps_the_application(self):
        with mock.patch("apps.careers.services.EmailMessage.send", side_effect=OSError("smtp down")):
            self.assertEqual(self.apply().status_code, 201)
        self.assertTrue(Application.objects.exists())

    def test_limits_applications_per_email(self):
        for _ in range(3):
            self.assertEqual(self.apply().status_code, 201)
        self.assertEqual(self.apply().status_code, 429)
        self.assertEqual(self.apply(email="someone@example.org").status_code, 201)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ApplicationInboxTests(APITestCase):
    def setUp(self):
        self.editor = User.objects.create_user(username="editor1", password="pw12345", role="editor")
        self.researcher = User.objects.create_user(username="researcher", password="pw12345", role="researcher")
        self.application = Application.objects.create(
            kind="internship", full_name="Ravi", email="ravi@example.org", cv=pdf(), cover_letter=pdf("letter.pdf")
        )

    def test_staff_list_applications_without_file_links(self):
        self.client.force_authenticate(self.editor)
        row = self.client.get("/api/v1/applications/").data["results"][0]
        self.assertEqual((row["full_name"], row["kind"], row["status"]), ("Ravi", "internship", "new"))
        self.assertNotIn("cv", row)
        self.assertNotIn("cover_letter", row)
        self.assertFalse(row["has_writing_sample"])

    def test_staff_open_the_cv_cover_letter_and_writing_sample(self):
        self.client.force_authenticate(self.editor)
        url = f"/api/v1/applications/{self.application.pk}/files/"
        self.assertEqual(self.client.get(f"{url}writing_sample/").status_code, 404)
        self.application.writing_sample = pdf("essay.pdf")
        self.application.save()
        for document in ["cv", "cover_letter", "writing_sample"]:
            response = self.client.get(f"{url}{document}/")
            self.assertEqual(response.status_code, 200)
            self.assertIn("/applications/", response.data["file"])
        self.assertEqual(self.client.get(f"{url}sop/").status_code, 404)
        self.assertTrue(self.client.get("/api/v1/applications/").data["results"][0]["has_writing_sample"])

    def test_others_cannot_see_applications_or_their_files(self):
        for user in [None, self.researcher]:
            self.client.force_authenticate(user)
            with self.subTest(user=user):
                self.assertIn(self.client.get("/api/v1/applications/").status_code, (401, 403))
                files = self.client.get(f"/api/v1/applications/{self.application.pk}/files/cv/")
                self.assertIn(files.status_code, (401, 403))

    def test_marking_reviewed_records_who_and_audits(self):
        self.client.force_authenticate(self.editor)
        url = f"/api/v1/applications/{self.application.pk}/"
        response = self.client.patch(url, {"status": "reviewed", "full_name": "Changed"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.application.refresh_from_db()
        self.assertEqual((self.application.status, self.application.full_name), ("reviewed", "Ravi"))
        self.assertEqual(self.application.handled_by, self.editor)
        self.assertTrue(AuditLog.objects.filter(action="application_status", module="careers").exists())


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class JobOpeningTests(APITestCase):
    def test_editors_create_openings_that_appear_once_published(self):
        editor = User.objects.create_user(username="editor1", password="pw12345", role="editor")
        self.client.force_authenticate(editor)
        response = self.client.post(
            "/api/v1/jobs/", {"slug": "ra", "title": "Research Associate", "display_order": 1}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["rolling"])
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/v1/jobs/").data["results"], [])
        JobOpening.objects.filter(slug="ra").update(status="published", published_at=timezone.now())
        self.assertEqual(self.client.get("/api/v1/jobs/ra/").data["title"], "Research Associate")

    def opening(self):
        editor = User.objects.create_user(username="editor2", password="pw12345", role="editor")
        self.client.force_authenticate(editor)
        response = self.client.post("/api/v1/jobs/", {"slug": "research-assistant", "title": "Research Assistant",
                                                      "writing_sample": "required"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return editor

    def test_editors_upload_a_job_description_pdf_the_public_can_read(self):
        self.opening()
        response = self.client.patch("/api/v1/jobs/research-assistant/",
                                     {"description_pdf": pdf("jd.pdf")}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("/jobs/", response.data["description_pdf"])
        self.assertEqual(response.data["writing_sample"], "required")
        JobOpening.objects.filter(slug="research-assistant").update(status="published", published_at=timezone.now())
        self.client.force_authenticate(None)
        self.assertIn("/jobs/", self.client.get("/api/v1/jobs/research-assistant/").data["description_pdf"])

    def test_the_job_description_must_be_a_real_pdf_and_null_removes_it(self):
        self.opening()
        url = "/api/v1/jobs/research-assistant/"
        for bad in [SimpleUploadedFile("jd.docx", DOCX), pdf("jd.pdf", b"MZ\x90\x00 not a pdf")]:
            response = self.client.patch(url, {"description_pdf": bad}, format="multipart")
            self.assertEqual(response.status_code, 400, bad.name)
        self.client.patch(url, {"description_pdf": pdf("jd.pdf")}, format="multipart")
        response = self.client.patch(url, {"description_pdf": None}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["description_pdf"])

    def test_writing_sample_defaults_to_optional(self):
        self.assertEqual(JobOpening.objects.model._meta.get_field("writing_sample").default, "optional")


class InitialOpeningsMigrationTests(APITestCase):
    migration = import_module("apps.careers.migrations.0002_initial_openings")

    def test_creates_the_two_rolling_openings_once(self):
        User.objects.create_user(username="admin1", password="pw12345", role="admin")
        self.migration.create_openings(apps, None)
        self.migration.create_openings(apps, None)
        openings = JobOpening.objects.order_by("display_order")
        self.assertEqual([o.slug for o in openings], ["research-associate", "data-analyst"])
        self.assertTrue(all(o.rolling and o.status == "published" for o in openings))

    def test_skips_a_database_without_users(self):
        self.migration.create_openings(apps, None)
        self.assertFalse(JobOpening.objects.exists())


class JobDescriptionsMigrationTests(APITestCase):
    def add(self):
        import_module("apps.careers.migrations.0003_job_descriptions").add_descriptions(apps, None)

    def test_fills_only_empty_descriptions(self):
        owner = get_user_model().objects.create_user(username="owner7", password="pw12345", role="admin")
        JobOpening.objects.create(slug="research-associate", title="Research Associate", created_by=owner)
        JobOpening.objects.create(
            slug="data-analyst", title="Data Analyst", description="Staff's own text.", created_by=owner
        )
        self.add()
        self.add()
        self.assertTrue(JobOpening.objects.get(slug="research-associate").description.startswith("## What you'll do"))
        self.assertEqual(JobOpening.objects.get(slug="data-analyst").description, "Staff's own text.")

    def test_has_no_em_dashes(self):
        descriptions = import_module("apps.careers.migrations.0003_job_descriptions").DESCRIPTIONS
        for text in descriptions.values():
            self.assertNotIn("—", text)
