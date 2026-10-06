import os
import subprocess
import sys
from unittest import mock

from django.conf import settings
from django.db import OperationalError
from django.test import TestCase, override_settings


class HealthCheckTests(TestCase):
    def test_healthz_is_public_and_reports_ok(self):
        response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_healthz_returns_503_when_database_is_unreachable(self):
        with mock.patch("config.health.connection.cursor", side_effect=OperationalError("db down")):
            response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 503)


class ContainerHealthcheckTests(TestCase):
    def test_addresses_the_check_to_the_first_allowed_host(self):
        from config.healthcheck import health_host

        self.assertEqual(health_host("api-staging.priresearch.in"), "api-staging.priresearch.in")
        self.assertEqual(health_host(" .priresearch.in , localhost"), "priresearch.in")
        self.assertEqual(health_host("*"), "localhost")
        self.assertEqual(health_host(""), "localhost")

    @override_settings(ALLOWED_HOSTS=["api.example.org"])
    def test_the_chosen_host_passes_django_host_validation(self):
        from config.healthcheck import health_host

        self.assertEqual(self.client.get("/healthz/", HTTP_HOST="127.0.0.1:8000").status_code, 400)
        self.assertEqual(self.client.get("/healthz/", HTTP_HOST=health_host("api.example.org")).status_code, 200)


def _load_settings(**overrides):
    """Import config.settings in a fresh interpreter so module-level guards run against exactly these env vars."""
    env = {k: v for k, v in os.environ.items() if k not in {"ENVIRONMENT", "DEBUG", "SECRET_KEY"}}
    env.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings",
            "AWS_STORAGE_BUCKET_NAME": "",
            "DATABASE_URL": "sqlite:///:memory:",
            **overrides,
        }
    )
    code = "from django.conf import settings; print(settings.SECURE_SSL_REDIRECT, settings.SESSION_COOKIE_SECURE)"
    return subprocess.run(
        [sys.executable, "-c", code], cwd=settings.BASE_DIR, env=env, capture_output=True, text=True, timeout=60
    )


class DeployedEnvironmentGuardTests(TestCase):
    def test_production_with_valid_config_enables_https_hardening(self):
        result = _load_settings(
            ENVIRONMENT="production", DEBUG="False", SECRET_KEY="x" * 50, AWS_STORAGE_BUCKET_NAME="pri-prod"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["True", "True"])

    def test_production_without_bucket_is_rejected(self):
        result = _load_settings(ENVIRONMENT="production", DEBUG="False", SECRET_KEY="x" * 50)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("AWS_STORAGE_BUCKET_NAME is required", result.stderr)

    def test_staging_with_debug_on_is_rejected(self):
        result = _load_settings(
            ENVIRONMENT="staging", DEBUG="True", SECRET_KEY="x" * 50, AWS_STORAGE_BUCKET_NAME="pri-staging"
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DEBUG must be False", result.stderr)

    def test_debug_off_without_secret_key_is_rejected(self):
        result = _load_settings(ENVIRONMENT="dev", DEBUG="False", SECRET_KEY="")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SECRET_KEY", result.stderr)

    def test_unknown_environment_name_is_rejected(self):
        result = _load_settings(ENVIRONMENT="prod", DEBUG="False", SECRET_KEY="x" * 50)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ENVIRONMENT must be", result.stderr)

    def test_dev_keeps_https_redirect_off(self):
        result = _load_settings(ENVIRONMENT="dev", DEBUG="True")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["False", "False"])
