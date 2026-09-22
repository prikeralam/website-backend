from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from apps.taxonomy.models import Theme

from .models import AccessRequest, Dataset

# The PRD's own highest-priority test (docs/PRDs/C-data-repository-dashboard-integration.md:54):
# an internal_only or un-approved on_request dataset must never be reachable via any endpoint
# by an unauthorized role. This suite covers the 3 visibility tiers x the relevant roles.


class DatasetVisibilityTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.public_user = User.objects.create_user(username="visitor", password="pw12345", role="public")
        self.researcher = User.objects.create_user(username="researcher", password="pw12345", role="researcher")
        self.editor = User.objects.create_user(username="editor", password="pw12345", role="editor")
        self.admin = User.objects.create_user(username="admin", password="pw12345", role="admin")
        health = Theme.objects.get(slug="health")
        sub_theme = Theme.objects.create(slug="maternal-health", name="Maternal Health", parent=health)

        def make_dataset(slug, visibility):
            return Dataset.objects.create(
                slug=slug,
                title=slug,
                file=SimpleUploadedFile(f"{slug}.csv", b"a,b\n1,2\n"),
                format="csv",
                sub_theme=sub_theme,
                visibility=visibility,
                created_by=self.admin,
            )

        self.public_ds = make_dataset("public-ds", "public")
        self.on_request_ds = make_dataset("on-request-ds", "on_request")
        self.internal_ds = make_dataset("internal-ds", "internal_only")

    def _list_slugs(self, user):
        self.client.force_authenticate(user)
        response = self.client.get("/api/v1/datasets/")
        return {item["slug"] for item in response.data["results"]}

    def test_public_role_never_sees_internal_only(self):
        slugs = self._list_slugs(self.public_user)
        self.assertIn("public-ds", slugs)
        self.assertIn("on-request-ds", slugs)
        self.assertNotIn("internal-ds", slugs)

    def test_public_role_detail_404s_on_internal_only(self):
        self.client.force_authenticate(self.public_user)
        response = self.client.get("/api/v1/datasets/internal-ds/")
        self.assertEqual(response.status_code, 404)

    def test_researcher_can_see_internal_only(self):
        slugs = self._list_slugs(self.researcher)
        self.assertIn("internal-ds", slugs)

    def test_editor_can_see_internal_only(self):
        slugs = self._list_slugs(self.editor)
        self.assertIn("internal-ds", slugs)

    def test_public_dataset_downloadable_by_any_authenticated_user(self):
        self.client.force_authenticate(self.public_user)
        response = self.client.get("/api/v1/datasets/public-ds/download/")
        self.assertEqual(response.status_code, 200)

    def test_on_request_dataset_blocked_without_approval(self):
        self.client.force_authenticate(self.public_user)
        response = self.client.get("/api/v1/datasets/on-request-ds/download/")
        self.assertEqual(response.status_code, 403)

    def test_on_request_dataset_downloadable_after_approval(self):
        AccessRequest.objects.create(user=self.public_user, dataset=self.on_request_ds, status="approved")
        self.client.force_authenticate(self.public_user)
        response = self.client.get("/api/v1/datasets/on-request-ds/download/")
        self.assertEqual(response.status_code, 200)

    def test_internal_only_download_blocked_for_public_role(self):
        # internal_only is genuinely invisible to non-internal-use roles (not just
        # download-gated), so this 404s the same way the detail endpoint does — the
        # dataset doesn't exist from this user's perspective at all.
        self.client.force_authenticate(self.public_user)
        response = self.client.get("/api/v1/datasets/internal-ds/download/")
        self.assertEqual(response.status_code, 404)

    def test_internal_only_downloadable_by_researcher(self):
        self.client.force_authenticate(self.researcher)
        response = self.client.get("/api/v1/datasets/internal-ds/download/")
        self.assertEqual(response.status_code, 200)

    def test_internal_only_downloadable_by_staff(self):
        self.client.force_authenticate(self.editor)
        response = self.client.get("/api/v1/datasets/internal-ds/download/")
        self.assertEqual(response.status_code, 200)


class AccessRequestFlowTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.requester = User.objects.create_user(username="requester", password="pw12345", role="public")
        self.editor = User.objects.create_user(username="editor2", password="pw12345", role="editor")
        governance = Theme.objects.get(slug="governance")
        sub_theme = Theme.objects.create(slug="gov-transparency-2", name="Transparency", parent=governance)
        self.dataset = Dataset.objects.create(
            slug="gated-ds",
            title="Gated",
            file=SimpleUploadedFile("gated.csv", b"a,b\n1,2\n"),
            format="csv",
            sub_theme=sub_theme,
            visibility="on_request",
            created_by=self.editor,
        )

    def test_request_access_creates_pending_request(self):
        self.client.force_authenticate(self.requester)
        response = self.client.post(f"/api/v1/datasets/{self.dataset.slug}/request-access/")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "pending")

    def test_non_staff_cannot_see_access_request_queue(self):
        AccessRequest.objects.create(user=self.requester, dataset=self.dataset)
        self.client.force_authenticate(self.requester)
        response = self.client.get("/api/v1/access-requests/")
        self.assertEqual(response.status_code, 403)

    def test_staff_can_approve_access_request(self):
        access_request = AccessRequest.objects.create(user=self.requester, dataset=self.dataset)
        self.client.force_authenticate(self.editor)
        response = self.client.patch(
            f"/api/v1/access-requests/{access_request.pk}/", {"status": "approved"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        access_request.refresh_from_db()
        self.assertEqual(access_request.status, "approved")
        self.assertEqual(access_request.reviewed_by, self.editor)


class DatasetTablePreviewTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(
            username="researcher3", password="pw12345", role="researcher"
        )
        migration_theme = Theme.objects.get(slug="migration")
        sub_theme = Theme.objects.create(slug="internal-migration", name="Internal Migration", parent=migration_theme)
        self.csv_ds = Dataset.objects.create(
            slug="csv-ds",
            title="CSV",
            file=SimpleUploadedFile("data.csv", b"col1,col2\n1,2\n3,4\n"),
            format="csv",
            sub_theme=sub_theme,
            visibility="public",
            created_by=self.user,
        )
        self.parquet_ds = Dataset.objects.create(
            slug="parquet-ds",
            title="Parquet",
            file=SimpleUploadedFile("data.parquet", b"not-real-parquet"),
            format="parquet",
            sub_theme=sub_theme,
            visibility="public",
            created_by=self.user,
        )

    def test_csv_preview_returns_rows(self):
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/v1/datasets/csv-ds/preview/table/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["header"], ["col1", "col2"])
        self.assertEqual(response.data["rows"], [["1", "2"], ["3", "4"]])

    def test_parquet_preview_not_implemented(self):
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/v1/datasets/parquet-ds/preview/table/")
        self.assertEqual(response.status_code, 501)

    def test_map_preview_not_implemented(self):
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/v1/datasets/csv-ds/preview/map/")
        self.assertEqual(response.status_code, 501)


class DatasetSubThemeRequirementTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(
            username="researcher4", password="pw12345", role="researcher"
        )
        self.client.force_authenticate(self.user)
        self.top_level_theme = Theme.objects.get(slug="demography")
        self.sub_theme = Theme.objects.create(slug="fertility-rates", name="Fertility Rates", parent=self.top_level_theme)

    def _payload(self, sub_theme_id):
        return {
            "slug": "demo-dataset",
            "title": "Demo Dataset",
            "file": SimpleUploadedFile("demo.csv", b"a,b\n1,2\n"),
            "format": "csv",
            "sub_theme": sub_theme_id,
        }

    def test_top_level_theme_rejected_as_sub_theme(self):
        response = self.client.post("/api/v1/datasets/", self._payload(self.top_level_theme.pk), format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("sub_theme", response.data)

    def test_actual_sub_theme_accepted(self):
        response = self.client.post("/api/v1/datasets/", self._payload(self.sub_theme.pk), format="multipart")
        self.assertEqual(response.status_code, 201)

    def test_theme_filter_returns_datasets_under_any_of_its_subthemes(self):
        other_sub = Theme.objects.create(slug="mortality-rates", name="Mortality Rates", parent=self.top_level_theme)
        Dataset.objects.create(
            slug="demo-ds-1", title="D1", file=SimpleUploadedFile("d1.csv", b"a\n1\n"),
            format="csv", sub_theme=self.sub_theme, visibility="public", created_by=self.user,
        )
        Dataset.objects.create(
            slug="demo-ds-2", title="D2", file=SimpleUploadedFile("d2.csv", b"a\n1\n"),
            format="csv", sub_theme=other_sub, visibility="public", created_by=self.user,
        )
        response = self.client.get(f"/api/v1/datasets/?theme={self.top_level_theme.pk}")
        slugs = {item["slug"] for item in response.data["results"]}
        self.assertEqual(slugs, {"demo-ds-1", "demo-ds-2"})
