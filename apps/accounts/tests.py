import io
import re
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog
from apps.accounts.services import guard_admin_lockout
from apps.content.models import ContentBlock, Document, PersonProfile
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

    def test_uses_the_real_annual_report_and_board_photos(self):
        seed()
        self.assertGreater(Document.objects.get(slug="annual-report-2025-26").file.size, 100_000)
        chairman = PersonProfile.objects.get(name="Sayyid Sadiq Ali Shihab")
        self.assertTrue(chairman.photo_url.endswith("/people/executive/sayyid-sadiq-ali-shihab.jpg"))
        self.assertFalse(PersonProfile.objects.filter(group="patron", photo_url="").exists())

    @override_settings(FRONTEND_URL="https://staging.example.org")
    def test_person_photos_come_from_this_environments_frontend(self):
        seed()
        photos = PersonProfile.objects.exclude(photo_url="").values_list("photo_url", flat=True)
        self.assertTrue(photos)
        for url in photos:
            self.assertTrue(url.startswith("https://staging.example.org/people/"), url)

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


class TokenAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        get_user_model().objects.create_user(username="alice", email="alice@example.com", password="right-pass-123")

    def login(self, username="alice", password="right-pass-123"):
        return self.client.post("/api/v1/token/", {"username": username, "password": password}, format="json")

    def test_login_is_throttled_per_username(self):
        for _ in range(5):
            self.assertEqual(self.login(password="wrong").status_code, 401)
        self.assertEqual(self.login().status_code, 429)
        # Another account is unaffected, although every request comes from the same IP.
        get_user_model().objects.create_user(username="bob", password="right-pass-123")
        self.assertEqual(self.login(username="bob").status_code, 200)

    def test_throttle_ignores_username_case_and_padding(self):
        for _ in range(5):
            self.login(username=" ALICE ", password="wrong")
        self.assertEqual(self.login().status_code, 429)

    def post(self, path, refresh):
        return self.client.post(path, {"refresh": refresh}, format="json").status_code

    def test_logout_revokes_the_refresh_token(self):
        refresh = self.login().json()["refresh"]
        self.assertEqual(self.post("/api/v1/token/refresh/", refresh), 200)
        self.assertEqual(self.post("/api/v1/token/logout/", refresh), 200)
        self.assertEqual(self.post("/api/v1/token/refresh/", refresh), 401)

    def test_logout_rejects_an_invalid_token(self):
        self.assertEqual(self.post("/api/v1/token/logout/", "not-a-token"), 401)


ROLES = ["public", "researcher", "editor", "fellow", "admin"]


class UserManagementTestCase(TestCase):
    """Issue #38: the admin user-management API, the /users/me/ endpoints and password resets."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.users = {
            role: User.objects.create_user(
                username=f"{role}_user", email=f"{role}@example.com", password="right-pass-123", role=role
            )
            for role in ROLES
        }
        cls.admin = cls.users["admin"]

    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def as_admin(self):
        return self.as_user(self.admin)

    def audit_rows(self, action):
        return list(AuditLog.objects.filter(module="accounts", action=action))

    def login(self, username, password="right-pass-123"):
        return APIClient().post("/api/v1/token/", {"username": username, "password": password}, format="json")


class AdminOnlyTests(UserManagementTestCase):
    def test_every_admin_endpoint_refuses_other_roles_and_anonymous(self):
        target = self.users["public"].pk
        endpoints = [
            ("get", "/api/v1/users/"),
            ("get", f"/api/v1/users/{target}/"),
            ("post", "/api/v1/users/"),
            ("patch", f"/api/v1/users/{target}/"),
            ("post", f"/api/v1/users/{target}/deactivate/"),
            ("post", f"/api/v1/users/{target}/reactivate/"),
            ("post", f"/api/v1/users/{target}/send-password-reset/"),
            ("patch", f"/api/v1/users/{target}/role/"),
        ]
        for method, url in endpoints:
            with self.subTest(method=method, url=url, caller="anonymous"):
                self.assertEqual(getattr(APIClient(), method)(url, {}, format="json").status_code, 401)
            for role in ["public", "researcher", "editor", "fellow"]:
                with self.subTest(method=method, url=url, caller=role):
                    client = self.as_user(self.users[role])
                    self.assertEqual(getattr(client, method)(url, {}, format="json").status_code, 403)

    def test_users_cannot_be_deleted_or_replaced(self):
        url = f"/api/v1/users/{self.users['public'].pk}/"
        self.assertEqual(self.as_admin().delete(url).status_code, 405)
        self.assertEqual(self.as_admin().put(url, {}, format="json").status_code, 405)


class ListAndDetailTests(UserManagementTestCase):
    def test_list_filters_by_role_and_active_state_and_searches(self):
        client = self.as_admin()
        editors = client.get("/api/v1/users/?role=editor").json()["results"]
        self.assertEqual([u["username"] for u in editors], ["editor_user"])
        self.users["fellow"].is_active = False
        self.users["fellow"].save()
        inactive = client.get("/api/v1/users/?is_active=false").json()["results"]
        self.assertEqual([u["username"] for u in inactive], ["fellow_user"])
        found = client.get("/api/v1/users/?q=RESEARCHER@").json()["results"]
        self.assertEqual([u["username"] for u in found], ["researcher_user"])

    def test_responses_never_include_secrets(self):
        client = self.as_admin()
        rows = client.get("/api/v1/users/").json()["results"] + [client.get("/api/v1/users/me/").json()]
        for row in rows:
            self.assertEqual(
                set(row),
                {"id", "username", "email", "first_name", "last_name", "role",
                 "is_active", "must_change_password", "date_joined", "last_login"},
            )

    def test_me_is_not_mistaken_for_a_user_id(self):
        response = self.as_user(self.users["public"]).get("/api/v1/users/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "public_user")


class CreateUserTests(UserManagementTestCase):
    def create(self, **fields):
        data = {"username": "newbie", "email": "newbie@example.com", "first_name": "New", "role": "researcher"}
        data.update(fields)
        return self.as_admin().post("/api/v1/users/", data, format="json")

    def test_temporary_password_user_must_change_it(self):
        response = self.create(password="Temp-pass-4821")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(response.json()["must_change_password"])
        self.assertNotIn("password", response.json())
        self.assertEqual(len(mail.outbox), 0)
        login = self.login("newbie", "Temp-pass-4821")
        self.assertEqual(login.status_code, 200)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")
        change = client.post(
            "/api/v1/users/me/password/",
            {"old_password": "Temp-pass-4821", "new_password": "My-own-pass-9373"},
            format="json",
        )
        self.assertEqual(change.status_code, 204)
        self.assertFalse(client.get("/api/v1/users/me/").json()["must_change_password"])

    def test_weak_temporary_password_is_rejected(self):
        response = self.create(password="123")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json())
        self.assertFalse(get_user_model().objects.filter(username="newbie").exists())

    def test_without_a_password_the_user_is_emailed_an_invite(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.content)
        user = get_user_model().objects.get(username="newbie")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["newbie@example.com"])
        self.assertIn("invited", mail.outbox[0].subject)

        uid, token = link_params(mail.outbox[0].body)
        confirm = APIClient().post(
            "/api/v1/password-reset/confirm/",
            {"uid": uid, "token": token, "new_password": "Chosen-pass-5512"},
            format="json",
        )
        self.assertEqual(confirm.status_code, 204)
        self.assertEqual(self.login("newbie", "Chosen-pass-5512").status_code, 200)

    def test_invited_user_cannot_sign_in_before_setting_a_password(self):
        self.create()
        for password in ["", "!", "anything"]:
            with self.subTest(password=password):
                self.assertIn(self.login("newbie", password).status_code, (400, 401))

    def test_email_must_be_unique_and_present(self):
        self.assertEqual(self.create(email="EDITOR@example.com").status_code, 400)
        self.assertEqual(self.create(email="").status_code, 400)

    def test_creation_is_audited_without_the_password(self):
        self.create(password="Temp-pass-4821")
        (row,) = self.audit_rows("user_create")
        self.assertEqual(row.actor, self.admin)
        self.assertEqual(row.metadata, {"role": "researcher", "invite": False})
        self.assertEqual(row.target, f"user:{get_user_model().objects.get(username='newbie').pk}")

    def test_creating_an_admin_grants_admin_site_access(self):
        self.create(role="admin", password="Temp-pass-4821")
        user = get_user_model().objects.get(username="newbie")
        self.assertTrue(user.is_staff and user.is_superuser)


class EditUserTests(UserManagementTestCase):
    def test_admin_edits_contact_details_but_not_role_or_state(self):
        target = self.users["researcher"]
        response = self.as_admin().patch(
            f"/api/v1/users/{target.pk}/",
            {"first_name": "Rafi", "email": "rafi@example.com", "role": "admin", "is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        target.refresh_from_db()
        self.assertEqual(
            (target.first_name, target.email, target.role, target.is_active),
            ("Rafi", "rafi@example.com", "researcher", True),
        )
        (row,) = self.audit_rows("user_update")
        self.assertEqual(
            row.metadata,
            {"changes": {"first_name": ["", "Rafi"], "email": ["researcher@example.com", "rafi@example.com"]}},
        )

    def test_user_edits_own_profile_but_not_role(self):
        client = self.as_user(self.users["fellow"])
        response = client.patch("/api/v1/users/me/", {"last_name": "K", "role": "admin"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.json()["last_name"], response.json()["role"]), ("K", "fellow"))

    def test_own_password_change_needs_the_current_password(self):
        client = self.as_user(self.users["editor"])
        response = client.post(
            "/api/v1/users/me/password/",
            {"old_password": "wrong", "new_password": "Brand-new-pass-771"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


class DeactivationTests(UserManagementTestCase):
    def test_deactivated_user_is_locked_out_everywhere(self):
        target = self.users["editor"]
        tokens = self.login("editor_user").json()
        response = self.as_admin().post(f"/api/v1/users/{target.pk}/deactivate/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_active"])

        self.assertEqual(self.login("editor_user").status_code, 401)
        refresh = APIClient().post("/api/v1/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(refresh.status_code, 401)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(client.get("/api/v1/users/me/").status_code, 401)

    def test_reactivation_restores_access_and_both_are_audited(self):
        url = f"/api/v1/users/{self.users['editor'].pk}"
        self.as_admin().post(f"{url}/deactivate/")
        self.as_admin().post(f"{url}/deactivate/")  # already inactive: no second audit row
        self.as_admin().post(f"{url}/reactivate/")
        self.assertEqual(self.login("editor_user").status_code, 200)
        self.assertEqual(len(self.audit_rows("user_deactivate")), 1)
        self.assertEqual(len(self.audit_rows("user_reactivate")), 1)


class AdminLockoutTests(UserManagementTestCase):
    def test_admin_cannot_demote_or_deactivate_themselves(self):
        client = self.as_admin()
        demote = client.patch(f"/api/v1/users/{self.admin.pk}/role/", {"role": "editor"}, format="json")
        deactivate = client.post(f"/api/v1/users/{self.admin.pk}/deactivate/")
        self.assertEqual((demote.status_code, deactivate.status_code), (400, 400))
        self.admin.refresh_from_db()
        self.assertEqual((self.admin.role, self.admin.is_active), ("admin", True))
        self.assertEqual(self.audit_rows("role_change") + self.audit_rows("user_deactivate"), [])

    def test_another_admin_can_be_demoted_or_deactivated_while_one_remains(self):
        User = get_user_model()
        second = User.objects.create_user(username="second", email="s@example.com", role="admin")
        third = User.objects.create_user(username="third", email="t@example.com", role="admin")
        client = self.as_admin()
        demote = client.patch(f"/api/v1/users/{second.pk}/role/", {"role": "editor"}, format="json")
        deactivate = client.post(f"/api/v1/users/{third.pk}/deactivate/")
        self.assertEqual((demote.status_code, deactivate.status_code), (200, 200))

    def test_the_last_active_admin_can_never_be_removed(self):
        # Through the API the caller is always another active admin, so this rule is checked on
        # the guard itself: it protects the account whichever caller reaches it.
        outsider = get_user_model()(pk=0, role="admin")
        with self.assertRaises(ValidationError):
            guard_admin_lockout(outsider, self.admin)


class RoleDrivesAdminSiteTests(UserManagementTestCase):
    def test_promotion_and_demotion_through_the_api_follow_the_role(self):
        target = self.users["editor"]
        url = f"/api/v1/users/{target.pk}/role/"
        self.as_admin().patch(url, {"role": "admin"}, format="json")
        target.refresh_from_db()
        self.assertTrue(target.is_staff and target.is_superuser)
        self.as_admin().patch(url, {"role": "editor"}, format="json")
        target.refresh_from_db()
        self.assertFalse(target.is_staff or target.is_superuser)

    def test_createsuperuser_makes_an_admin(self):
        user = get_user_model().objects.create_superuser("root", "root@example.com", "root-pass-123")
        self.assertEqual(user.role, "admin")


class PasswordResetTests(UserManagementTestCase):
    def request_reset(self, email):
        return APIClient().post("/api/v1/password-reset/", {"email": email}, format="json")

    def confirm(self, uid, token, new_password="Reset-pass-6620"):
        data = {"uid": uid, "token": token, "new_password": new_password}
        return APIClient().post("/api/v1/password-reset/confirm/", data, format="json")

    def test_unknown_email_gets_the_same_answer_and_no_mail(self):
        self.assertEqual(self.request_reset("nobody@example.com").status_code, 204)
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_link_works_once(self):
        self.assertEqual(self.request_reset("EDITOR@example.com").status_code, 204)
        self.assertEqual(len(mail.outbox), 1)
        uid, token = link_params(mail.outbox[0].body)
        self.assertEqual(self.confirm(uid, token).status_code, 204)
        self.assertEqual(self.confirm(uid, token, "Another-pass-3391").status_code, 400)
        self.assertEqual(self.login("editor_user", "Reset-pass-6620").status_code, 200)

    def test_tampered_link_is_refused(self):
        self.assertEqual(self.confirm("MQ", "abc-123").status_code, 400)
        self.assertEqual(self.confirm("not-base64!", "abc-123").status_code, 400)

    def test_inactive_users_get_no_reset_mail(self):
        self.users["editor"].is_active = False
        self.users["editor"].save()
        self.request_reset("editor@example.com")
        self.assertEqual(len(mail.outbox), 0)

    def test_requests_are_throttled_per_email(self):
        for _ in range(5):
            self.request_reset("editor@example.com")
        self.assertEqual(self.request_reset("editor@example.com").status_code, 429)
        self.assertEqual(self.request_reset("fellow@example.com").status_code, 204)

    def test_admin_can_send_a_reset_and_it_is_audited(self):
        response = self.as_admin().post(f"/api/v1/users/{self.users['fellow'].pk}/send-password-reset/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(mail.outbox[0].to, ["fellow@example.com"])
        self.assertIn("Reset", mail.outbox[0].subject)
        self.assertEqual(len(self.audit_rows("password_reset_sent")), 1)

    def test_reset_clears_must_change_password(self):
        target = self.users["public"]
        target.must_change_password = True
        target.save()
        self.request_reset("public@example.com")
        self.confirm(*link_params(mail.outbox[0].body))
        target.refresh_from_db()
        self.assertFalse(target.must_change_password)


def link_params(body):
    query = parse_qs(urlparse(re.search(r"http\S+/reset-password\?\S+", body).group(0)).query)
    return query["uid"][0], query["token"][0]
