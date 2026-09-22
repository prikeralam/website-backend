from rest_framework.test import APITestCase

from .models import Theme


class ThemeCrudPermissionTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.researcher = User.objects.create_user(username="researcher", password="pw12345", role="researcher")
        self.editor = User.objects.create_user(username="editor", password="pw12345", role="editor")
        self.education = Theme.objects.get(slug="education")

    def test_any_authenticated_user_can_list(self):
        self.client.force_authenticate(self.researcher)
        response = self.client.get("/api/v1/themes/")
        self.assertEqual(response.status_code, 200)

    def test_researcher_cannot_create(self):
        self.client.force_authenticate(self.researcher)
        response = self.client.post("/api/v1/themes/", {"slug": "new-theme", "name": "New Theme"})
        self.assertEqual(response.status_code, 403)

    def test_editor_can_create(self):
        self.client.force_authenticate(self.editor)
        response = self.client.post("/api/v1/themes/", {"slug": "new-theme", "name": "New Theme"})
        self.assertEqual(response.status_code, 201)

    def test_editor_can_delete(self):
        self.client.force_authenticate(self.editor)
        extra = Theme.objects.create(slug="deletable", name="Deletable")
        response = self.client.delete(f"/api/v1/themes/{extra.pk}/")
        self.assertEqual(response.status_code, 204)


class SubThemeTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.editor = get_user_model().objects.create_user(username="editor2", password="pw12345", role="editor")
        self.client.force_authenticate(self.editor)
        self.education = Theme.objects.get(slug="education")
        self.health = Theme.objects.get(slug="health")

    def test_create_subtheme_under_top_level(self):
        response = self.client.post(
            "/api/v1/themes/", {"slug": "primary-education", "name": "Primary Education", "parent": self.education.pk}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["parent"], self.education.pk)

    def test_subtheme_cannot_have_its_own_subtheme(self):
        sub = Theme.objects.create(slug="primary-ed", name="Primary Ed", parent=self.education)
        response = self.client.post(
            "/api/v1/themes/", {"slug": "grade-1", "name": "Grade 1", "parent": sub.pk}
        )
        self.assertEqual(response.status_code, 400)

    def test_theme_cannot_be_its_own_parent(self):
        response = self.client.patch(f"/api/v1/themes/{self.education.pk}/", {"parent": self.education.pk})
        self.assertEqual(response.status_code, 400)

    def test_same_subtheme_name_allowed_under_different_parents(self):
        r1 = self.client.post("/api/v1/themes/", {"slug": "edu-other", "name": "Other", "parent": self.education.pk})
        r2 = self.client.post("/api/v1/themes/", {"slug": "health-other", "name": "Other", "parent": self.health.pk})
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)

    def test_duplicate_subtheme_name_under_same_parent_rejected(self):
        Theme.objects.create(slug="edu-primary", name="Primary", parent=self.education)
        response = self.client.post(
            "/api/v1/themes/", {"slug": "edu-primary-2", "name": "Primary", "parent": self.education.pk}
        )
        self.assertEqual(response.status_code, 400)

    def test_list_nests_subthemes(self):
        Theme.objects.create(slug="edu-primary-3", name="Primary Schooling", parent=self.education)
        response = self.client.get(f"/api/v1/themes/{self.education.pk}/")
        self.assertEqual(response.status_code, 200)
        slugs = [s["slug"] for s in response.data["subthemes"]]
        self.assertIn("edu-primary-3", slugs)

    def test_filter_by_parent(self):
        Theme.objects.create(slug="edu-primary-4", name="Primary Schooling 2", parent=self.education)
        response = self.client.get(f"/api/v1/themes/?parent={self.education.pk}")
        results = response.data["results"]
        self.assertTrue(all(r["parent"] == self.education.pk for r in results))
        self.assertTrue(len(results) >= 1)

    def test_filter_top_level_only(self):
        Theme.objects.create(slug="edu-primary-5", name="Primary Schooling 3", parent=self.education)
        response = self.client.get("/api/v1/themes/?top_level=true")
        results = response.data["results"]
        self.assertTrue(all(r["parent"] is None for r in results))
        self.assertGreaterEqual(len(results), 8)


class NestedSubThemeCrudTests(APITestCase):
    """/themes/{theme_pk}/subthemes/ — the dedicated nested CRUD resource, distinct from
    filtering the flat /themes/?parent= list."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.researcher = User.objects.create_user(username="researcher3", password="pw12345", role="researcher")
        self.editor = User.objects.create_user(username="editor3", password="pw12345", role="editor")
        self.education = Theme.objects.get(slug="education")
        self.health = Theme.objects.get(slug="health")

    def test_list_is_scoped_to_the_parent_theme(self):
        Theme.objects.create(slug="nested-edu-1", name="Nested Edu 1", parent=self.education)
        Theme.objects.create(slug="nested-health-1", name="Nested Health 1", parent=self.health)
        self.client.force_authenticate(self.researcher)
        response = self.client.get(f"/api/v1/themes/{self.education.pk}/subthemes/")
        self.assertEqual(response.status_code, 200)
        slugs = {s["slug"] for s in response.data["results"]}
        self.assertIn("nested-edu-1", slugs)
        self.assertNotIn("nested-health-1", slugs)

    def test_researcher_cannot_create(self):
        self.client.force_authenticate(self.researcher)
        response = self.client.post(
            f"/api/v1/themes/{self.education.pk}/subthemes/", {"slug": "nested-edu-2", "name": "Nested Edu 2"}
        )
        self.assertEqual(response.status_code, 403)

    def test_editor_can_create_and_parent_is_forced_from_url(self):
        self.client.force_authenticate(self.editor)
        response = self.client.post(
            f"/api/v1/themes/{self.education.pk}/subthemes/",
            # even if a client tries to pass a different parent, it's ignored — parent is read-only
            {"slug": "nested-edu-3", "name": "Nested Edu 3", "parent": self.health.pk},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["parent"], self.education.pk)

    def test_create_under_a_subtheme_404s(self):
        # theme_pk must itself be top-level — you can't nest a subtheme under a subtheme.
        sub = Theme.objects.create(slug="nested-edu-4", name="Nested Edu 4", parent=self.education)
        self.client.force_authenticate(self.editor)
        response = self.client.post(f"/api/v1/themes/{sub.pk}/subthemes/", {"slug": "x", "name": "X"})
        self.assertEqual(response.status_code, 404)

    def test_editor_can_update_and_delete(self):
        sub = Theme.objects.create(slug="nested-edu-5", name="Nested Edu 5", parent=self.education)
        self.client.force_authenticate(self.editor)
        patch_response = self.client.patch(
            f"/api/v1/themes/{self.education.pk}/subthemes/{sub.pk}/", {"name": "Renamed"}
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.data["name"], "Renamed")

        delete_response = self.client.delete(f"/api/v1/themes/{self.education.pk}/subthemes/{sub.pk}/")
        self.assertEqual(delete_response.status_code, 204)
