import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.content.models import ContentBlock
from apps.datarepo.models import Dataset
from apps.publications.models import Publication


def seed():
    call_command("seed_demo", stdout=io.StringIO())


class SeedDemoTests(TestCase):
    def test_creates_one_user_per_role_who_can_log_in(self):
        seed()
        roles = set(get_user_model().objects.filter(username__startswith="demo_").values_list("role", flat=True))
        self.assertEqual(roles, {"public", "researcher", "editor", "fellow", "admin"})
        response = APIClient().post(
            "/api/v1/token/", {"username": "demo_editor", "password": "demo-pass-123"}, format="json"
        )
        self.assertEqual(response.status_code, 200)

    def test_rerunning_does_not_duplicate_anything(self):
        seed()
        counts = (ContentBlock.objects.count(), Publication.objects.count(), Dataset.objects.count())
        seed()
        self.assertEqual(counts, (ContentBlock.objects.count(), Publication.objects.count(), Dataset.objects.count()))

    def test_anonymous_visitors_only_see_the_published_demo_content(self):
        seed()
        client = APIClient()
        blocks = {item["slug"] for item in client.get("/api/v1/content-blocks/").json()["results"]}
        self.assertIn("hero", blocks)
        self.assertNotIn("homepage-banner-draft", blocks)
        self.assertNotIn("annual-plan-2027", blocks)
        publications = {item["slug"] for item in client.get("/api/v1/publications/").json()["results"]}
        self.assertEqual(
            publications,
            {"malappuram-classrooms", "kerala-population-mix", "kerala-healthcare-gap", "kerala-gulf-migration"},
        )
        datasets = {item["slug"] for item in client.get("/api/v1/datasets/").json()["results"]}
        self.assertNotIn("enrolment-projection", datasets)
        self.assertIn("phc-load-by-area", datasets)

    def test_mirrors_the_prototype_people_and_projects(self):
        seed()
        client = APIClient()
        people = client.get("/api/v1/people/?group=team").json()["results"]
        self.assertEqual(len(people), 7)
        self.assertEqual(len(client.get("/api/v1/people/?group=executive").json()["results"]), 13)
        projects = {item["slug"] for item in client.get("/api/v1/projects/").json()["results"]}
        self.assertEqual(projects, {"sir-project", "education", "demography-migration"})

    def test_every_preview_format_works_on_the_demo_datasets(self):
        seed()
        client = APIClient()
        for slug in ["plus-one-batch-size", "religious-composition", "emigrants-by-community"]:
            with self.subTest(slug=slug):
                self.assertEqual(client.get(f"/api/v1/datasets/{slug}/preview/table/").status_code, 200)
        self.assertEqual(client.get("/api/v1/datasets/plus-one-batch-size-map/preview/map/").status_code, 200)

    @override_settings(ENVIRONMENT="staging")
    def test_refuses_to_run_outside_dev(self):
        with self.assertRaises(CommandError):
            seed()
        self.assertFalse(get_user_model().objects.filter(username__startswith="demo_").exists())
