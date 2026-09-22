from datetime import date

from rest_framework.test import APITestCase

from apps.taxonomy.models import Theme

from .models import Publication


class PublicationVisibilityTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="pw12345", role="researcher")
        self.other_researcher = User.objects.create_user(
            username="other", password="pw12345", role="researcher"
        )
        self.editor = User.objects.create_user(username="ed", password="pw12345", role="editor")
        education = Theme.objects.get(slug="education")
        self.sub_theme = Theme.objects.create(slug="primary-education", name="Primary Education", parent=education)

        self.private_pub = Publication.objects.create(
            slug="private-report",
            title="Private Report",
            abstract="x",
            format="report",
            sub_theme=self.sub_theme,
            date=date(2025, 1, 1),
            visibility="private",
            created_by=self.owner,
        )
        self.public_pub = Publication.objects.create(
            slug="public-report",
            title="Public Report",
            abstract="x",
            format="report",
            sub_theme=self.sub_theme,
            date=date(2025, 1, 1),
            visibility="public",
            created_by=self.owner,
        )

    def test_owner_can_see_own_private_publication(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/v1/publications/private-report/")
        self.assertEqual(response.status_code, 200)

    def test_other_researcher_cannot_see_private_publication(self):
        self.client.force_authenticate(self.other_researcher)
        response = self.client.get("/api/v1/publications/private-report/")
        self.assertEqual(response.status_code, 404)

    def test_staff_can_see_any_private_publication(self):
        self.client.force_authenticate(self.editor)
        response = self.client.get("/api/v1/publications/private-report/")
        self.assertEqual(response.status_code, 200)

    def test_public_publication_visible_to_all_authenticated_users(self):
        self.client.force_authenticate(self.other_researcher)
        response = self.client.get("/api/v1/publications/public-report/")
        self.assertEqual(response.status_code, 200)

    def test_private_publication_excluded_from_others_list(self):
        self.client.force_authenticate(self.other_researcher)
        response = self.client.get("/api/v1/publications/")
        slugs = [item["slug"] for item in response.data["results"]]
        self.assertNotIn("private-report", slugs)
        self.assertIn("public-report", slugs)


class CitationExportTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user(username="researcher", password="pw12345", role="researcher")
        self.client.force_authenticate(self.user)
        economics = Theme.objects.get(slug="economics")
        sub_theme = Theme.objects.create(slug="public-finance-sub", name="Fiscal Policy", parent=economics)
        self.pub = Publication.objects.create(
            slug="econ-brief",
            title="Economic Brief",
            abstract="x",
            format="brief",
            sub_theme=sub_theme,
            date=date(2025, 6, 1),
            external_id="pri-econ-2025-01",
            created_by=self.user,
        )

    def test_bibtex_format(self):
        response = self.client.get("/api/v1/publications/econ-brief/citation/?format=bibtex")
        self.assertEqual(response.status_code, 200)
        self.assertIn("@misc{pri-econ-2025-01", response.content.decode())

    def test_ris_format(self):
        response = self.client.get("/api/v1/publications/econ-brief/citation/?format=ris")
        self.assertEqual(response.status_code, 200)
        self.assertIn("TY  - RPRT", response.content.decode())

    def test_apa_format(self):
        response = self.client.get("/api/v1/publications/econ-brief/citation/?format=apa")
        self.assertEqual(response.status_code, 200)
        self.assertIn("(2025)", response.content.decode())

    def test_unsupported_format_rejected(self):
        response = self.client.get("/api/v1/publications/econ-brief/citation/?format=mla")
        self.assertEqual(response.status_code, 400)


class SubThemeRequirementTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(
            username="researcher2", password="pw12345", role="researcher"
        )
        self.client.force_authenticate(self.user)
        self.top_level_theme = Theme.objects.get(slug="governance")
        self.sub_theme = Theme.objects.create(slug="gov-transparency", name="Transparency", parent=self.top_level_theme)

    def _payload(self, sub_theme_id):
        return {
            "slug": "gov-report",
            "title": "Governance Report",
            "abstract": "x",
            "format": "report",
            "sub_theme": sub_theme_id,
            "date": "2025-01-01",
        }

    def test_top_level_theme_rejected_as_sub_theme(self):
        response = self.client.post("/api/v1/publications/", self._payload(self.top_level_theme.pk))
        self.assertEqual(response.status_code, 400)
        self.assertIn("sub_theme", response.data)

    def test_actual_sub_theme_accepted(self):
        response = self.client.post("/api/v1/publications/", self._payload(self.sub_theme.pk))
        self.assertEqual(response.status_code, 201)

    def test_theme_filter_returns_publications_under_any_of_its_subthemes(self):
        other_sub = Theme.objects.create(slug="gov-elections", name="Elections", parent=self.top_level_theme)
        Publication.objects.create(
            slug="gov-report-1", title="R1", abstract="x", format="report",
            sub_theme=self.sub_theme, date="2025-01-01", created_by=self.user,
        )
        Publication.objects.create(
            slug="gov-report-2", title="R2", abstract="x", format="report",
            sub_theme=other_sub, date="2025-01-01", created_by=self.user,
        )
        response = self.client.get(f"/api/v1/publications/?theme={self.top_level_theme.pk}")
        slugs = {item["slug"] for item in response.data["results"]}
        self.assertEqual(slugs, {"gov-report-1", "gov-report-2"})
