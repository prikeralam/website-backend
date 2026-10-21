import io
import json
import os
import tempfile
import zipfile
from unittest import mock

import pyarrow as pa
import pyarrow.parquet as pq
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase, override_settings
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
                status="published",
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

    def test_public_dataset_downloadable_once_the_email_is_confirmed(self):
        self.client.force_authenticate(self.public_user)
        self.assertEqual(self.client.get("/api/v1/datasets/public-ds/download/").status_code, 403)
        self.public_user.email_verified = True
        self.public_user.save(update_fields=["email_verified"])
        self.assertEqual(self.client.get("/api/v1/datasets/public-ds/download/").status_code, 200)

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
            status="published",
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

        self.user = get_user_model().objects.create_user(username="researcher3", password="pw12345", role="researcher")
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
        self.sub_theme = sub_theme

    def _dataset(self, slug, filename, content, fmt):
        return Dataset.objects.create(
            slug=slug,
            title=slug,
            file=SimpleUploadedFile(filename, content),
            format=fmt,
            sub_theme=self.sub_theme,
            visibility="public",
            created_by=self.user,
        )

    @staticmethod
    def _parquet_bytes(rows):
        buffer = io.BytesIO()
        pq.write_table(pa.table({"id": list(range(rows)), "name": [f"n{i}" for i in range(rows)]}), buffer)
        return buffer.getvalue()

    @staticmethod
    def _zip_bytes(members):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, content in members.items():
                archive.writestr(name, content)
        return buffer.getvalue()

    def test_csv_preview_returns_rows(self):
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/v1/datasets/csv-ds/preview/table/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["header"], ["col1", "col2"])
        self.assertEqual(response.data["rows"], [["1", "2"], ["3", "4"]])

    def test_parquet_preview_returns_header_and_rows(self):
        self._dataset("parquet-ds", "data.parquet", self._parquet_bytes(3), "parquet")
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/v1/datasets/parquet-ds/preview/table/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["header"], ["id", "name"])
        self.assertEqual(response.data["rows"], [[0, "n0"], [1, "n1"], [2, "n2"]])

    def test_parquet_preview_second_page(self):
        self._dataset("parquet-ds", "data.parquet", self._parquet_bytes(60), "parquet")
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/v1/datasets/parquet-ds/preview/table/?page=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row[0] for row in response.data["rows"]], list(range(50, 60)))

    def test_corrupt_parquet_preview_is_unprocessable(self):
        self._dataset("parquet-ds", "data.parquet", b"not-real-parquet", "parquet")
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/v1/datasets/parquet-ds/preview/table/")
        self.assertEqual(response.status_code, 422)

    def test_zip_preview_reads_first_csv_member(self):
        content = self._zip_bytes({"readme.txt": "hi", "a.csv": "x,y\n1,2\n", "b.csv": "z\n9\n"})
        self._dataset("zip-ds", "data.zip", content, "zip")
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/v1/datasets/zip-ds/preview/table/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["header"], ["x", "y"])
        self.assertEqual(response.data["rows"], [["1", "2"]])

    def test_zip_without_csv_is_unprocessable(self):
        self._dataset("zip-ds", "data.zip", self._zip_bytes({"readme.txt": "hi"}), "zip")
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/v1/datasets/zip-ds/preview/table/")
        self.assertEqual(response.status_code, 422)

    def test_corrupt_zip_is_unprocessable(self):
        self._dataset("zip-ds", "data.zip", b"not-a-zip", "zip")
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/v1/datasets/zip-ds/preview/table/")
        self.assertEqual(response.status_code, 422)

    def test_internal_only_parquet_stays_hidden_from_public_role(self):
        dataset = self._dataset("parquet-ds", "data.parquet", self._parquet_bytes(1), "parquet")
        dataset.visibility = "internal_only"
        dataset.save(update_fields=["visibility"])
        from django.contrib.auth import get_user_model

        visitor = get_user_model().objects.create_user(username="visitor9", password="pw12345", role="public")
        self.client.force_authenticate(visitor)
        response = self.client.get("/api/v1/datasets/parquet-ds/preview/table/")
        self.assertEqual(response.status_code, 404)


class DatasetMapPreviewTests(APITestCase):
    FEATURE_COLLECTION = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"name": "A"}, "geometry": {"type": "Point", "coordinates": [77.2, 28.6]}}
        ],
    }

    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(username="mapper", password="pw12345", role="researcher")
        self.sub_theme = Theme.objects.create(
            slug="internal-migration", name="Internal Migration", parent=Theme.objects.get(slug="migration")
        )

    def _dataset(self, slug, content, fmt="geojson", visibility="public"):
        return Dataset.objects.create(
            slug=slug,
            title=slug,
            file=SimpleUploadedFile(f"{slug}.{fmt}", content),
            format=fmt,
            sub_theme=self.sub_theme,
            visibility=visibility,
            created_by=self.user,
        )

    def _get(self, slug, user=None):
        self.client.force_authenticate(user or self.user)
        return self.client.get(f"/api/v1/datasets/{slug}/preview/map/")

    def test_geojson_is_served_as_is(self):
        self._dataset("geo", json.dumps(self.FEATURE_COLLECTION).encode())
        response = self._get("geo")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), self.FEATURE_COLLECTION)

    def test_non_spatial_format_is_unprocessable(self):
        self._dataset("plain", b"a,b\n1,2\n", fmt="csv")
        self.assertEqual(self._get("plain").status_code, 422)

    def test_invalid_json_is_unprocessable(self):
        self._dataset("broken", b"{not json")
        self.assertEqual(self._get("broken").status_code, 422)

    def test_json_that_is_not_geojson_is_unprocessable(self):
        self._dataset("other", b'{"hello": "world"}')
        self.assertEqual(self._get("other").status_code, 422)

    def test_oversized_file_is_rejected(self):
        self._dataset("big", json.dumps(self.FEATURE_COLLECTION).encode())
        with mock.patch("apps.datarepo.geo.MAX_GEOJSON_BYTES", 10):
            self.assertEqual(self._get("big").status_code, 413)

    def test_internal_only_geojson_stays_hidden_from_public_role(self):
        from django.contrib.auth import get_user_model

        self._dataset("secret", json.dumps(self.FEATURE_COLLECTION).encode(), visibility="internal_only")
        visitor = get_user_model().objects.create_user(username="visitor10", password="pw12345", role="public")
        self.assertEqual(self._get("secret", user=visitor).status_code, 404)

    def test_geojson_has_no_table_preview(self):
        self._dataset("geo", json.dumps(self.FEATURE_COLLECTION).encode())
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get("/api/v1/datasets/geo/preview/table/").status_code, 501)


class DatasetSubThemeRequirementTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(username="researcher4", password="pw12345", role="researcher")
        self.client.force_authenticate(self.user)
        self.top_level_theme = Theme.objects.get(slug="demography")
        self.sub_theme = Theme.objects.create(
            slug="fertility-rates", name="Fertility Rates", parent=self.top_level_theme
        )

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
            slug="demo-ds-1",
            title="D1",
            file=SimpleUploadedFile("d1.csv", b"a\n1\n"),
            format="csv",
            sub_theme=self.sub_theme,
            visibility="public",
            created_by=self.user,
        )
        Dataset.objects.create(
            slug="demo-ds-2",
            title="D2",
            file=SimpleUploadedFile("d2.csv", b"a\n1\n"),
            format="csv",
            sub_theme=other_sub,
            visibility="public",
            created_by=self.user,
        )
        response = self.client.get(f"/api/v1/datasets/?theme={self.top_level_theme.pk}")
        slugs = {item["slug"] for item in response.data["results"]}
        self.assertEqual(slugs, {"demo-ds-1", "demo-ds-2"})


class DatasetFileStatsTests(APITestCase):
    """Row and column stats are worked out from the file whenever it changes, and never block a save."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        self.admin = get_user_model().objects.create_user(username="admin", password="pw12345", role="admin")
        health = Theme.objects.get(slug="health")
        self.sub_theme = Theme.objects.create(slug="stats-sub", name="Stats Sub", parent=health)

    def _dataset(self, name, content, fmt, **extra):
        return Dataset.objects.create(
            slug=name.split(".")[0],
            title=name,
            file=SimpleUploadedFile(name, content),
            format=fmt,
            sub_theme=self.sub_theme,
            visibility="public",
            status="published",
            created_by=self.admin,
            **extra,
        )

    def test_counts_rows_and_names_columns_for_each_format(self):
        table = pa.table({"district": ["Malappuram", "Kollam"], "seats": [65, 40]})
        parquet = io.BytesIO()
        pq.write_table(table, parquet)
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("__MACOSX/a.csv", "junk\n")
            z.writestr("data.csv", "a,b,c\n1,2,3\n4,5,6\n7,8,9\n")
        geojson = json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"district": "A", "value": 1}, "geometry": None},
                    {"type": "Feature", "properties": {"district": "B", "note": "x"}, "geometry": None},
                ],
            }
        ).encode()

        cases = [
            ("csv-ds.csv", b"x,y\n1,2\n3,4\n", "csv", 2, ["x", "y"]),
            # Excel and pri-data write UTF-8 with a byte-order mark; it must not end up in the first column name
            ("bom-ds.csv", "﻿ജില്ല,y\n1,2\n".encode(), "csv", 1, ["ജില്ല", "y"]),
            ("parquet-ds.parquet", parquet.getvalue(), "parquet", 2, ["district", "seats"]),
            ("zip-ds.zip", archive.getvalue(), "zip", 3, ["a", "b", "c"]),
            ("geo-ds.geojson", geojson, "geojson", 2, ["district", "value", "note"]),
        ]
        for name, content, fmt, rows, columns in cases:
            with self.subTest(fmt=fmt):
                dataset = self._dataset(name, content, fmt)
                dataset.refresh_from_db()
                stats = (dataset.row_count, dataset.column_count, dataset.columns)
                self.assertEqual(stats, (rows, len(columns), columns))

    def test_an_unreadable_file_leaves_stats_empty_without_failing(self):
        dataset = self._dataset("broken.parquet", b"not parquet", "parquet")
        dataset.refresh_from_db()
        self.assertEqual((dataset.row_count, dataset.column_count, dataset.columns), (None, None, []))

    def test_recomputes_when_the_file_changes_but_not_on_other_edits(self):
        dataset = self._dataset("changing.csv", b"a\n1\n", "csv")
        dataset = Dataset.objects.get(pk=dataset.pk)
        with mock.patch("apps.datarepo.previews.profile_file") as profile:
            dataset.title = "Renamed"
            dataset.save()
            profile.assert_not_called()
        dataset.file = SimpleUploadedFile("changing2.csv", b"a,b\n1,2\n3,4\n5,6\n")
        dataset.save()
        dataset.refresh_from_db()
        self.assertEqual((dataset.row_count, dataset.columns), (3, ["a", "b"]))

    def test_api_shows_the_new_fields_and_keeps_stats_read_only(self):
        extra = {"granularity": "District, Year", "time_period": "2014-15 to 2024-25"}
        dataset = self._dataset("api-ds.csv", b"a,b\n1,2\n", "csv", **extra)
        self.client.force_authenticate(self.admin)
        body = self.client.get(f"/api/v1/datasets/{dataset.slug}/").data
        self.assertEqual(
            tuple(body[k] for k in ["granularity", "time_period", "citation", "row_count", "column_count", "columns"]),
            ("District, Year", "2014-15 to 2024-25", "", 1, 2, ["a", "b"]),
        )
        changes = {"row_count": 999, "citation": "PRI (2026)."}
        self.client.patch(f"/api/v1/datasets/{dataset.slug}/", changes, format="json")
        dataset.refresh_from_db()
        self.assertEqual((dataset.row_count, dataset.citation), (1, "PRI (2026)."))

    def test_themes_carry_a_description(self):
        health = Theme.objects.get(slug="health")
        health.description = "Public health in Kerala."
        health.save()
        body = self.client.get("/api/v1/themes/").data
        themes = body["results"] if isinstance(body, dict) else body
        self.assertEqual(next(t for t in themes if t["slug"] == "health")["description"], "Public health in Kerala.")


class CollectionTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.editor = User.objects.create_user(username="editor", password="pw12345", role="editor")
        self.visitor = User.objects.create_user(username="visitor", password="pw12345", role="public")
        health = Theme.objects.get(slug="health")
        sub = Theme.objects.create(slug="coll-sub", name="Coll Sub", parent=health)

        def dataset(slug, visibility, status="published"):
            return Dataset.objects.create(
                slug=slug,
                title=slug,
                file=SimpleUploadedFile(f"{slug}.csv", b"a\n1\n"),
                format="csv",
                sub_theme=sub,
                visibility=visibility,
                status=status,
                created_by=self.editor,
            )

        dataset("open-ds", "public")
        dataset("gated-ds", "on_request")
        dataset("internal-ds", "internal_only")
        dataset("draft-ds", "public", status="draft")

    def test_editor_creates_a_collection_by_dataset_slugs(self):
        self.client.force_authenticate(self.editor)
        data = {"slug": "plus-one", "title": "Plus One", "datasets": ["open-ds", "gated-ds", "internal-ds", "draft-ds"]}
        response = self.client.post("/api/v1/collections/", data, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(sorted(response.data["datasets"]), ["draft-ds", "gated-ds", "internal-ds", "open-ds"])

    def test_public_callers_never_see_draft_or_internal_datasets_in_a_collection(self):
        self.client.force_authenticate(self.editor)
        data = {"slug": "plus-one", "title": "Plus One", "datasets": ["open-ds", "gated-ds", "internal-ds", "draft-ds"]}
        self.client.post("/api/v1/collections/", data, format="json")
        for status in ("in_review", "approved", "published"):
            self.client.post("/api/v1/collections/plus-one/transition/", {"status": status}, format="json")

        for user in (None, self.visitor):
            with self.subTest(user=user):
                self.client.force_authenticate(user)
                body = self.client.get("/api/v1/collections/plus-one/").data
                self.assertEqual(sorted(body["datasets"]), ["gated-ds", "open-ds"])


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class DatasetFormatsTests(APITestCase):
    """One dataset, several formats of the same data: extra files share the dataset's access rules."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.visitor = User.objects.create_user(username="visitor", password="pw12345", role="public")
        self.reader = User.objects.create_user(
            username="reader", password="pw12345", role="public", email_verified=True
        )
        self.researcher = User.objects.create_user(username="researcher", password="pw12345", role="researcher")
        self.other = User.objects.create_user(username="other", password="pw12345", role="researcher")
        self.editor = User.objects.create_user(username="editor", password="pw12345", role="editor")
        health = Theme.objects.get(slug="health")
        self.sub = Theme.objects.create(slug="phc", name="PHC", parent=health)

    def dataset(self, slug, visibility="public", status="published", owner=None):
        return Dataset.objects.create(
            slug=slug,
            title=slug,
            file=SimpleUploadedFile(f"{slug}.csv", b"a,b\n1,2\n"),
            format="csv",
            sub_theme=self.sub,
            visibility=visibility,
            status=status,
            created_by=owner or self.editor,
        )

    def add(self, slug, fmt, user=None, content=b'[{"a": 1}]'):
        self.client.force_authenticate(user or self.editor)
        return self.client.post(
            f"/api/v1/datasets/{slug}/files/",
            {"format": fmt, "file": SimpleUploadedFile(f"{slug}.{fmt}", content)},
            format="multipart",
        )

    def test_files_list_the_main_file_then_other_formats(self):
        self.dataset("plus-one")
        self.assertEqual(self.add("plus-one", "json").status_code, 201)
        self.assertEqual(self.add("plus-one", "parquet", content=b"PAR1").status_code, 201)

        self.client.force_authenticate(self.reader)  # downloads need a confirmed account
        files = self.client.get("/api/v1/datasets/plus-one/").data["files"]
        self.assertEqual(
            [(f["format"], f["label"]) for f in files], [("csv", "CSV"), ("json", "JSON"), ("parquet", "Parquet")]
        )
        self.assertEqual(files[0]["size"], 8)
        self.assertEqual(files[1]["size"], 10)
        self.assertTrue(all(f["url"].startswith("http") for f in files))

    def test_download_picks_a_format(self):
        self.dataset("plus-one")
        self.add("plus-one", "json")
        self.client.force_authenticate(self.reader)
        self.assertTrue(self.client.get("/api/v1/datasets/plus-one/download/").data["file"].endswith(".csv"))
        self.assertTrue(
            self.client.get("/api/v1/datasets/plus-one/download/?format=json").data["file"].endswith(".json")
        )
        self.assertEqual(self.client.get("/api/v1/datasets/plus-one/download/?format=xlsx").status_code, 404)

    def test_other_formats_never_leak_past_the_access_rules(self):
        self.dataset("gated", visibility="on_request")
        self.add("gated", "json")
        for user in (None, self.visitor):
            with self.subTest(user=user):
                self.client.force_authenticate(user)
                body = self.client.get("/api/v1/datasets/gated/").data
                self.assertNotIn("files", body)
                self.assertNotIn("file", body)
                self.assertEqual(body["formats"], ["csv", "json"])
                self.assertEqual(self.client.get("/api/v1/datasets/gated/download/?format=json").status_code, 403)

        AccessRequest.objects.create(user=self.visitor, dataset=Dataset.objects.get(slug="gated"), status="approved")
        self.client.force_authenticate(self.visitor)
        self.assertEqual(
            [f["format"] for f in self.client.get("/api/v1/datasets/gated/").data["files"]], ["csv", "json"]
        )

    def test_one_file_per_format_and_not_the_main_format(self):
        self.dataset("plus-one")
        self.assertEqual(self.add("plus-one", "json").status_code, 201)
        self.assertEqual(self.add("plus-one", "json").status_code, 400)
        self.assertEqual(self.add("plus-one", "csv").status_code, 400)

    def test_only_people_who_may_edit_the_dataset_change_its_files(self):
        self.dataset("draft-ds", status="draft", owner=self.researcher)
        self.assertEqual(self.add("draft-ds", "json", user=self.other).status_code, 404)  # not visible to them at all
        self.assertEqual(self.add("draft-ds", "json", user=self.researcher).status_code, 201)

        self.dataset("published-ds", owner=self.researcher)
        self.assertEqual(self.add("published-ds", "json", user=self.researcher).status_code, 403)
        self.assertEqual(self.add("published-ds", "json", user=self.visitor).status_code, 403)
        self.client.force_authenticate(None)
        response = self.client.post("/api/v1/datasets/published-ds/files/", {"format": "json"}, format="multipart")
        self.assertEqual(response.status_code, 401)

    def test_removing_a_format_deletes_its_file_and_is_audited(self):
        from apps.accounts.models import AuditLog

        self.dataset("plus-one")
        file_id = self.add("plus-one", "json").data["id"]
        stored = Dataset.objects.get(slug="plus-one").extra_files.get().file
        path = stored.path
        self.assertTrue(os.path.exists(path))

        self.client.force_authenticate(self.visitor)
        self.assertEqual(self.client.delete(f"/api/v1/datasets/plus-one/files/{file_id}/").status_code, 403)
        self.client.force_authenticate(self.editor)
        self.assertEqual(self.client.delete(f"/api/v1/datasets/plus-one/files/{file_id}/").status_code, 204)
        self.assertFalse(os.path.exists(path))
        self.assertEqual(
            list(AuditLog.objects.filter(module="datarepo").values_list("action", flat=True).order_by("timestamp")),
            ["dataset_file_added", "dataset_file_removed"],
        )

    def test_deleting_the_dataset_deletes_its_other_formats(self):
        self.dataset("plus-one")
        self.add("plus-one", "json")
        path = Dataset.objects.get(slug="plus-one").extra_files.get().file.path
        Dataset.objects.get(slug="plus-one").delete()
        self.assertFalse(os.path.exists(path))


# PRI Data Framework publishing (website-backend #123: B1 fields, B2 publish gate, B3 two-person rule).
class DatasetPublishingFrameworkTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.pipeline = User.objects.create_user(username="pri-pipeline", password="pw12345", role="researcher")
        self.qa = User.objects.create_user(username="qa", password="pw12345", role="editor")
        self.lead = User.objects.create_user(username="lead", password="pw12345", role="editor")
        education = Theme.objects.get(slug="education")
        self.sub_theme = Theme.objects.create(slug="school-education", name="School Education", parent=education)

    def framework_fields(self):
        return {
            "code": "PRI-EDU-0002",
            "version": "1.0.0",
            "summary": "SSLC results by district",
            "description": "Results of the March 2026 SSLC exam.",
            "keywords": [" SSLC ", "exam results"],
            "source_publisher": "KITE / Pareeksha Bhavan",
            "source_document": "Saphalam results analysis",
            "source_url": "https://result.kite.kerala.gov.in/analysis/",
            "archived_url": "https://web.archive.org/web/2026/https://result.kite.kerala.gov.in/analysis/",
            "retrieval_date": "2026-10-15",
            "source_tier": "1",
            "collection_method": "administrative",
            "source_terms": "Not stated",
            "geography": "Kerala",
            "granularity": "District x management",
            "time_period": "2025-26",
            "period_type": "academic_year",
            "update_frequency": "Annual",
            "methodology": "1. Fetched. 2. Checked.",
            "known_limitations": "Only the latest exam.",
            "steward": "Data steward",
            "contact": "data@example.org",
            "lgd_levels": ["district"],
            "quality_grade": "A",
            "column_dictionary": [{"name": "a", "label": "A"}, {"name": "b", "label": "B", "unit": "students"}],
            "qa_report": {"passed": True, "grade_proposed": "A", "checks": []},
            "provenance": {"pipeline_repo": "pri-data", "git_sha": "abc"},
        }

    def create_as_pipeline(self, **extra):
        self.client.force_authenticate(self.pipeline)
        payload = {
            "slug": "sslc-results", "title": "SSLC results", "format": "csv", "sub_theme": self.sub_theme.pk,
            "file": SimpleUploadedFile("sslc.csv", b"a,b\n1,2\n"),
        }
        payload.update({k: json.dumps(v) if isinstance(v, (dict, list)) else v
                        for k, v in {**self.framework_fields(), **extra}.items()
                        if k not in ("keywords", "lgd_levels")})
        response = self.client.post("/api/v1/datasets/", payload, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        # list fields go as JSON (multipart can't carry a list cleanly), like the pipeline's PATCH will
        lists = {k: v for k, v in self.framework_fields().items() if k in ("keywords", "lgd_levels")}
        response = self.client.patch("/api/v1/datasets/sslc-results/", lists, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        return Dataset.objects.get(slug="sslc-results")

    def move(self, user, target, slug="sslc-results"):
        self.client.force_authenticate(user)
        return self.client.post(f"/api/v1/datasets/{slug}/transition/", {"status": target}, format="json")

    def complete_checklist(self, user=None):
        from .models import QA_CHECKLIST_ITEMS

        self.client.force_authenticate(user or self.qa)
        return self.client.patch(
            "/api/v1/datasets/sslc-results/", {"qa_checklist": {k: True for k, _ in QA_CHECKLIST_ITEMS}}, format="json"
        )

    def ready_for_publishing(self):
        dataset = self.create_as_pipeline()
        self.assertEqual(self.move(self.pipeline, "in_review").status_code, 200)
        self.assertEqual(self.complete_checklist().status_code, 200)
        self.assertEqual(self.move(self.qa, "approved").status_code, 200)
        return dataset

    # ------------------------------------------------------------------ B1
    def test_fields_round_trip_and_read_only_fields_are_ignored(self):
        dataset = self.create_as_pipeline()
        self.assertEqual(dataset.code, "PRI-EDU-0002")
        self.assertEqual(dataset.keywords, ["SSLC", "exam results"])
        self.assertEqual(dataset.license, "CC-BY-4.0")
        self.client.force_authenticate(self.qa)
        data = self.client.get("/api/v1/datasets/sslc-results/").data
        for field in ("summary", "source_tier", "period_type", "column_dictionary", "qa_report", "provenance"):
            self.assertEqual(data[field], json.loads(json.dumps(self.framework_fields()[field])))
        self.assertEqual(len(data["qa_checklist_items"]), 11)
        self.client.force_authenticate(self.pipeline)
        self.client.patch("/api/v1/datasets/sslc-results/", {"approved_by": self.lead.pk}, format="json")
        self.assertIsNone(Dataset.objects.get(slug="sslc-results").approved_by)

    def test_blank_code_is_stored_as_null_so_several_datasets_have_none(self):
        self.create_as_pipeline(code="")
        self.assertIsNone(Dataset.objects.get(slug="sslc-results").code)

    def test_field_validation(self):
        self.create_as_pipeline()
        cases = {
            "code": "EDU-2", "version": "1.0", "source_url": "http://example.org", "source_tier": "5",
            "keywords": ["ok", " "], "column_dictionary": [{"name": "a"}],
        }
        for field, bad in cases.items():
            response = self.client.patch("/api/v1/datasets/sslc-results/", {field: bad}, format="json")
            self.assertEqual(response.status_code, 400, field)
            self.assertIn(field, response.data)
        response = self.client.patch(
            "/api/v1/datasets/sslc-results/", {"column_dictionary": [{"name": "zzz", "label": "Z"}]}, format="json"
        )
        self.assertIn("Not columns of the file: zzz", str(response.data))

    def test_only_editors_write_the_qa_checklist(self):
        self.create_as_pipeline()
        response = self.client.patch("/api/v1/datasets/sslc-results/", {"qa_checklist": {"totals": True}},
                                     format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.complete_checklist().status_code, 200)
        self.client.force_authenticate(self.qa)
        response = self.client.patch("/api/v1/datasets/sslc-results/", {"qa_checklist": {"nonsense": True}},
                                     format="json")
        self.assertEqual(response.status_code, 400)

    def test_filters_and_search(self):
        self.create_as_pipeline()
        self.client.force_authenticate(self.qa)
        self.assertEqual(self.client.get("/api/v1/datasets/?code=PRI-EDU-0002").data["count"], 1)
        self.assertEqual(self.client.get("/api/v1/datasets/?source_tier=2").data["count"], 0)
        self.assertEqual(self.client.get("/api/v1/datasets/?quality_grade=A").data["count"], 1)
        self.assertEqual(self.client.get("/api/v1/datasets/?q=district").data["count"], 1)    # summary
        self.assertEqual(self.client.get("/api/v1/datasets/?q=exam%20results").data["count"], 1)  # keywords
        self.assertEqual(self.client.get("/api/v1/datasets/?q=rainfall").data["count"], 0)

    # ------------------------------------------------------------------ B2
    def test_complete_approved_dataset_publishes(self):
        self.ready_for_publishing()
        response = self.move(self.lead, "published")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Dataset.objects.get(slug="sslc-results").status, "published")

    def test_gate_names_each_missing_field(self):
        dataset = self.ready_for_publishing()
        Dataset.objects.filter(pk=dataset.pk).update(steward="", archived_url="")
        response = self.move(self.lead, "published")
        self.assertEqual(response.status_code, 400)
        self.assertIn("archived_url, steward", response.data["detail"])

    def test_gate_refusals(self):
        dataset = self.ready_for_publishing()
        for change, phrase in [
            ({"source_tier": "4"}, "tier 4"),
            ({"column_dictionary": [{"name": "a", "label": "A"}]}, "no label in the column dictionary: b"),
            ({"qa_report": {"passed": False}}, "QA report has not passed"),
            ({"qa_checklist": {"totals": True}}, "QA checklist is not complete"),
            ({"qa_checklist": {}}, "QA checklist is not complete"),
        ]:
            Dataset.objects.filter(pk=dataset.pk).update(**change)
            response = self.move(self.lead, "published")
            self.assertEqual(response.status_code, 400, change)
            self.assertIn(phrase, response.data["detail"])
            self.ready_state(dataset)

    def ready_state(self, dataset):
        from .models import QA_CHECKLIST_ITEMS

        fields = self.framework_fields()
        Dataset.objects.filter(pk=dataset.pk).update(
            source_tier="1", column_dictionary=fields["column_dictionary"], qa_report=fields["qa_report"],
            qa_checklist={k: True for k, _ in QA_CHECKLIST_ITEMS},
        )

    def test_publishing_only_from_approved(self):
        self.create_as_pipeline()
        self.move(self.pipeline, "in_review")
        self.complete_checklist()
        response = self.move(self.lead, "published")
        self.assertEqual(response.status_code, 400)
        self.assertIn("approved first", response.data["detail"])

    def test_old_published_dataset_stays_published_and_editable(self):
        old = Dataset.objects.create(
            slug="old", title="Old", file=SimpleUploadedFile("old.csv", b"a\n1\n"), format="csv",
            sub_theme=self.sub_theme, visibility="public", status="published", created_by=self.lead,
        )
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/v1/datasets/old/").status_code, 200)
        self.client.force_authenticate(self.qa)
        response = self.client.patch("/api/v1/datasets/old/", {"title": "Old, renamed"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Dataset.objects.get(pk=old.pk).status, "published")

    def test_an_edit_cannot_empty_a_required_field_of_a_published_dataset(self):
        self.ready_for_publishing()
        self.move(self.lead, "published")
        self.client.force_authenticate(self.qa)
        response = self.client.patch("/api/v1/datasets/sslc-results/", {"methodology": ""}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("methodology", response.data)

    # ------------------------------------------------------------------ B3
    def test_creator_cannot_approve(self):
        self.client.force_authenticate(self.qa)
        response = self.client.post("/api/v1/datasets/", {
            "slug": "by-editor", "title": "By editor", "format": "csv", "sub_theme": self.sub_theme.pk,
            "file": SimpleUploadedFile("e.csv", b"a\n1\n"),
        }, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.move(self.qa, "in_review", slug="by-editor")
        response = self.move(self.qa, "approved", slug="by-editor")
        self.assertEqual(response.status_code, 400)
        self.assertIn("another editor has to approve", response.data["detail"])

    def test_approver_cannot_publish_but_a_second_editor_can(self):
        self.ready_for_publishing()
        dataset = Dataset.objects.get(slug="sslc-results")
        self.assertEqual(dataset.approved_by, self.qa)
        self.assertIsNotNone(dataset.approved_at)
        response = self.move(self.qa, "published")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "You approved this dataset, so another editor has to publish it.")
        self.assertEqual(self.move(self.lead, "published").status_code, 200)

    def test_returning_to_draft_clears_the_approval(self):
        self.ready_for_publishing()
        self.assertEqual(self.move(self.lead, "draft").status_code, 200)
        dataset = Dataset.objects.get(slug="sslc-results")
        self.assertIsNone(dataset.approved_by)
        self.assertIsNone(dataset.approved_at)

    def test_the_pipeline_cannot_approve_or_publish(self):
        self.create_as_pipeline()
        self.move(self.pipeline, "in_review")
        self.assertEqual(self.move(self.pipeline, "approved").status_code, 403)
        self.assertEqual(self.move(self.pipeline, "published").status_code, 403)

    def test_every_transition_is_audited_with_three_different_actors(self):
        from apps.accounts.models import AuditLog

        dataset = self.ready_for_publishing()
        self.move(self.lead, "published")
        logs = AuditLog.objects.filter(action="status_transition", target=f"dataset:{dataset.pk}").order_by("id")
        self.assertEqual(
            [(log.actor.username, log.metadata["new_status"]) for log in logs],
            [("pri-pipeline", "in_review"), ("qa", "approved"), ("lead", "published")],
        )


class DatasetFrameworkMigrationTests(TransactionTestCase):
    """0009 adds every field as optional: existing datasets keep their values, stay published, get no license."""

    migrate_from = [("datarepo", "0008_dataset_download")]
    migrate_to = [("datarepo", "0009_dataset_publishing_framework")]

    def test_existing_rows_survive(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        from django.contrib.auth import get_user_model

        DatasetOld = old_apps.get_model("datarepo", "Dataset")
        # Only datarepo is rolled back, so the user and theme tables are the current ones.
        user = get_user_model().objects.create_user(username="old-admin", password="pw12345", role="admin")
        sub = Theme.objects.create(slug="old-sub", name="Old sub", parent=Theme.objects.get(slug="health"))
        DatasetOld.objects.create(slug="kept", title="Kept", file="datasets/kept.csv", format="csv",
                                  sub_theme_id=sub.pk, status="published", visibility="public", source="Census",
                                  created_by_id=user.pk)

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.migrate_to)
        new_apps = executor.loader.project_state(self.migrate_to).apps
        kept = new_apps.get_model("datarepo", "Dataset").objects.get(slug="kept")
        self.assertEqual((kept.status, kept.source, kept.title), ("published", "Census", "Kept"))
        self.assertEqual((kept.license, kept.code, kept.keywords, kept.qa_report), ("", None, [], {}))

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())
