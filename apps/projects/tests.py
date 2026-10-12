import tempfile

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Project


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ProjectStageTests(APITestCase):
    def setUp(self):
        editor = get_user_model().objects.create_user(username="editor1", password="pw12345", role="editor")
        self.client.force_authenticate(editor)

    def create(self, **extra):
        return self.client.post("/api/v1/projects/", {"slug": "p", "title": "P", "blurb": "B", **extra}, format="json")

    def test_new_projects_are_ongoing(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["stage"], Project.Stage.ONGOING)

    def test_stage_can_be_set_to_completed(self):
        response = self.create(stage="completed")
        self.assertEqual(response.data["stage"], "completed")

    def test_rejects_an_unknown_stage(self):
        response = self.create(stage="paused")
        self.assertEqual(response.status_code, 400)
        self.assertIn("stage", response.data)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ProjectDetailsTests(APITestCase):
    def setUp(self):
        editor = get_user_model().objects.create_user(username="editor1", password="pw12345", role="editor")
        self.client.force_authenticate(editor)

    def create(self, **extra):
        return self.client.post("/api/v1/projects/", {"slug": "p", "title": "P", "blurb": "B", **extra}, format="json")

    def test_facts_and_details_default_to_empty(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["facts"], [])
        self.assertEqual(response.data["details"], "")

    def test_saves_trimmed_facts_and_details(self):
        response = self.create(
            facts=["  Project duration: 2025 - 2026 "], details="\nOverview.\n\n## Section\n\nText.\n"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["facts"], ["Project duration: 2025 - 2026"])
        self.assertEqual(response.data["details"], "Overview.\n\n## Section\n\nText.")

    def test_rejects_empty_fact_lines(self):
        response = self.create(facts=["Lead: PRI", " "])
        self.assertEqual(response.status_code, 400)
        self.assertIn("facts", response.data)

    def test_rejects_too_many_facts(self):
        response = self.create(facts=[f"Fact {i}: x" for i in range(13)])
        self.assertEqual(response.status_code, 400)

    def test_rejects_overlong_details(self):
        response = self.create(details="x" * 40_001)
        self.assertEqual(response.status_code, 400)
        self.assertIn("details", response.data)


class ProjectWriteupMigrationTests(APITestCase):
    def test_writeups_cover_the_seeded_projects_without_em_dashes(self):
        from importlib import import_module

        writeups = import_module("apps.projects.migrations.0007_project_writeups").PROJECTS
        self.assertEqual(set(writeups), {"sir-project", "education", "demography-migration"})
        for fields in writeups.values():
            text = " ".join([fields["title"], fields["blurb"], fields["details"], *fields["facts"]])
            self.assertNotIn("—", text)
            self.assertNotIn("Policy Research Institute", text)
            self.assertLessEqual(len(fields["details"]), 40_000)
