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
