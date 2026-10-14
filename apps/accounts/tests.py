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

    def test_login_records_last_login(self):
        self.assertEqual(self.login().status_code, 200)
        self.assertIsNotNone(get_user_model().objects.get(username="alice").last_login)

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
            ("get", "/api/v1/users/stats/"),
            ("get", "/api/v1/users/export/"),
            ("get", f"/api/v1/users/{target}/downloads/"),
            ("post", f"/api/v1/users/{target}/resend-verification/"),
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
                 "is_active", "must_change_password", "date_joined", "last_login",
                 "email_verified", "organisation", "purpose", "newsletter_opt_in", "download_count"},
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


@override_settings(FRONTEND_URL="https://pri.example")
class VisitorSignupTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()  # throttle counters live in the cache
        self.client = APIClient()

    def register(self, **overrides):
        body = {
            "email": "Reader@Example.org",
            "password": "a-long-pass-phrase-9",
            "first_name": "Asha",
            "last_name": "K",
            "organisation": "Calicut University",
            "purpose": "research",
            "newsletter_opt_in": True,
            "next": "/data/plus-one-batch-size",
            **overrides,
        }
        # The confirmation email goes out once the new account is committed.
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post("/api/v1/register/", body, format="json")

    def link_params(self):
        url = re.search(r"https://pri\.example/\S+", mail.outbox[-1].body).group(0)
        return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}

    def test_signup_creates_an_unconfirmed_visitor_and_emails_a_link_back_to_the_dataset(self):
        response = self.register()
        self.assertEqual(response.status_code, 202)
        user = get_user_model().objects.get(email="reader@example.org")
        self.assertEqual((user.username, user.role, user.email_verified), ("reader@example.org", "public", False))
        answers = (user.organisation, user.purpose, user.newsletter_opt_in)
        self.assertEqual(answers, ("Calicut University", "research", True))
        self.assertEqual(mail.outbox[-1].to, ["reader@example.org"])
        self.assertEqual(self.link_params()["next"], "/data/plus-one-batch-size")

    def test_an_unsafe_next_is_dropped_from_the_link(self):
        self.register(next="https://evil.example/")
        self.assertNotIn("next", self.link_params())
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_an_existing_address_gets_the_same_answer_and_a_sign_in_email_instead(self):
        self.register()
        response = self.register(email="READER@example.org", password="another-long-pass-7")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"detail": "Check your inbox: we've sent you an email to finish signing up."})
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(mail.outbox[-1].subject, "You already have a PRI account")

    def test_weak_passwords_and_missing_fields_are_refused(self):
        self.assertIn("password", self.register(password="123").json())
        self.assertIn("purpose", self.register(email="b@example.org", purpose="spying").json())
        self.assertIn("first_name", self.register(email="c@example.org", first_name="").json())
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_signups_are_throttled_per_address(self):
        for _ in range(5):
            self.register()
        self.assertEqual(self.register().status_code, 429)

    def test_the_link_confirms_the_email_once(self):
        self.register()
        params = self.link_params()
        body = {"uid": params["uid"], "token": params["token"]}
        self.assertEqual(self.client.post("/api/v1/verify-email/", body, format="json").status_code, 204)
        self.assertTrue(get_user_model().objects.get(email="reader@example.org").email_verified)
        self.assertEqual(self.client.post("/api/v1/verify-email/", body, format="json").status_code, 400)

    def test_a_tampered_link_is_refused(self):
        self.register()
        params = self.link_params()
        response = self.client.post("/api/v1/verify-email/", {"uid": params["uid"], "token": "x-y"}, format="json")
        self.assertEqual(response.status_code, 400)

    def login(self, username, password):
        return self.client.post("/api/v1/token/", {"username": username, "password": password}, format="json")

    def test_visitors_sign_in_with_their_email_and_staff_with_their_username(self):
        self.register()
        self.assertEqual(self.login("READER@example.org", "a-long-pass-phrase-9").status_code, 200)
        get_user_model().objects.create_user(username="staffer", email="staff@example.org", password="pw12345-long")
        for name in ["staffer", "staff@example.org"]:
            with self.subTest(name=name):
                self.assertEqual(self.login(name, "pw12345-long").status_code, 200)

    def test_an_email_shared_by_two_accounts_cannot_sign_in_by_email(self):
        User = get_user_model()
        User.objects.create_user(username="one", email="shared@example.org", password="pw12345-long")
        User.objects.create_user(username="two", email="Shared@example.org", password="pw12345-long")
        self.assertEqual(self.login("shared@example.org", "pw12345-long").status_code, 401)

    def test_resend_sends_a_new_link_only_while_unconfirmed(self):
        self.register()
        user = get_user_model().objects.get(email="reader@example.org")
        self.client.force_authenticate(user)
        sent = len(mail.outbox)
        self.assertEqual(self.client.post("/api/v1/users/me/resend-verification/", {}, format="json").status_code, 204)
        self.assertEqual(len(mail.outbox), sent + 1)
        user.email_verified = True
        user.save(update_fields=["email_verified"])
        self.client.post("/api/v1/users/me/resend-verification/", {}, format="json")
        self.assertEqual(len(mail.outbox), sent + 1)

    def test_me_shows_and_edits_the_signup_answers_but_not_the_confirmation(self):
        self.register()
        user = get_user_model().objects.get(email="reader@example.org")
        self.client.force_authenticate(user)
        body = {"newsletter_opt_in": False, "email_verified": True}
        data = self.client.patch("/api/v1/users/me/", body, format="json").json()
        self.assertEqual((data["newsletter_opt_in"], data["email_verified"]), (False, False))

    def test_accounts_made_by_admins_count_as_confirmed(self):
        admin = get_user_model().objects.create_user(username="boss", password="pw12345-long", role="admin")
        self.client.force_authenticate(admin)
        response = self.client.post(
            "/api/v1/users/", {"username": "newbie", "email": "newbie@example.org", "role": "researcher"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(get_user_model().objects.get(username="newbie").email_verified)


class VisitorsAdminTests(UserManagementTestCase):
    """Issue #111: visitor filters, figures, the CSV export and per-user downloads."""

    def setUp(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.datarepo.models import Dataset
        from apps.taxonomy.models import Theme

        User = get_user_model()
        self.reader = User.objects.create_user(
            username="reader@example.org", email="reader@example.org", password="x-long-pass-1", role="public",
            first_name="=Rita", organisation="Calicut University", purpose="research",
            newsletter_opt_in=True, email_verified=True,
        )
        self.lurker = User.objects.create_user(
            username="lurker@example.org", email="lurker@example.org", password="x-long-pass-1", role="public",
            organisation="calicut university", purpose="journalism",
        )
        theme = Theme.objects.filter(parent__isnull=False).first() or Theme.objects.first()
        self.dataset = Dataset.objects.create(
            slug="open-ds", title="Open data", status="published", visibility="public", format="csv",
            sub_theme=theme, created_by=self.admin, file=SimpleUploadedFile("open.csv", b"a,b\n1,2\n"),
        )

    def download(self, user):
        return self.as_user(user).get("/api/v1/datasets/open-ds/download/")

    def test_downloads_are_recorded_for_accounts_only(self):
        from apps.datarepo.models import DatasetDownload

        self.assertEqual(self.download(self.reader).status_code, 200)
        self.assertEqual(self.download(self.lurker).status_code, 403)  # email not confirmed
        self.assertEqual(APIClient().get("/api/v1/datasets/open-ds/download/").status_code, 403)
        recorded = list(DatasetDownload.objects.values_list("user__email", "format"))
        self.assertEqual(recorded, [("reader@example.org", "csv")])
        rows = self.as_admin().get(f"/api/v1/users/{self.reader.pk}/downloads/").json()
        self.assertEqual([(r["dataset"], r["format"]) for r in rows], [("open-ds", "csv")])

    def test_list_filters_and_orders_visitors(self):
        client = self.as_admin()
        base = "/api/v1/users/?role=public"
        names = lambda q: [u["username"] for u in client.get(base + q).json()["results"]]  # noqa: E731
        self.assertEqual(set(names("")), {"public_user", "reader@example.org", "lurker@example.org"})
        self.assertEqual(names("&email_verified=true&newsletter_opt_in=true"), ["reader@example.org"])
        self.assertEqual(names("&purpose=journalism"), ["lurker@example.org"])
        self.download(self.reader)
        rows = client.get(base + "&ordering=-date_joined&page_size=2").json()
        self.assertEqual(len(rows["results"]), 2)
        counts = {u["username"]: u["download_count"] for u in client.get(base).json()["results"]}
        self.assertEqual(counts["reader@example.org"], 1)

    def test_stats_count_visitors_purposes_organisations_and_downloads(self):
        self.download(self.reader)
        stats = self.as_admin().get("/api/v1/users/stats/").json()
        self.assertEqual(stats["visitors"]["total"], 3)
        self.assertEqual((stats["visitors"]["confirmed"], stats["visitors"]["newsletter"]), (1, 1))
        self.assertEqual(len(stats["weekly_signups"]), 12)
        self.assertEqual(sum(w["count"] for w in stats["weekly_signups"]), 3)
        self.assertEqual(stats["top_organisations"][0], {"organisation": "Calicut University", "count": 2})
        self.assertIn({"purpose": "research", "label": "Research", "count": 1}, stats["purposes"])
        self.assertEqual(stats["downloads"]["total"], 1)
        self.assertEqual(stats["downloads"]["top_datasets"], [{"slug": "open-ds", "title": "Open data", "count": 1}])

    def test_export_is_csv_safe_for_spreadsheets_and_audited(self):
        response = self.as_admin().get("/api/v1/users/export/?role=public&newsletter_only=true")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertIn("pri-newsletter-", response["Content-Disposition"])
        lines = response.content.decode("utf-8-sig").strip().splitlines()
        self.assertTrue(lines[0].startswith("Name,Email,Organisation"))
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[1].startswith("'=Rita"))  # a formula-like name can't run in Excel
        row = AuditLog.objects.get(action="users_export")
        self.assertEqual((row.actor, row.metadata["rows"], row.metadata["newsletter_only"]), (self.admin, 1, True))

    def test_staff_filter_leaves_visitors_out(self):
        client = self.as_admin()
        staff = {u["role"] for u in client.get("/api/v1/users/?staff=true&page_size=100").json()["results"]}
        self.assertNotIn("public", staff)
        visitors = {u["role"] for u in client.get("/api/v1/users/?staff=false&page_size=100").json()["results"]}
        self.assertEqual(visitors, {"public"})

    def test_admin_can_resend_a_visitors_confirmation_once_needed(self):
        client = self.as_admin()
        self.assertEqual(client.post(f"/api/v1/users/{self.lurker.pk}/resend-verification/").status_code, 204)
        self.assertEqual(mail.outbox[-1].to, ["lurker@example.org"])
        self.assertEqual(client.post(f"/api/v1/users/{self.reader.pk}/resend-verification/").status_code, 400)
        self.assertEqual(len(self.audit_rows("verification_resent")), 1)
