from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import AuditLog

from .models import ContactMessage

User = get_user_model()


def message_data(**extra):
    return {
        "category": "research",
        "name": "Asha",
        "email": "asha@example.org",
        "message": "I'd like to discuss your Plus One study.",
        **extra,
    }


@override_settings(CONTACT_EMAIL="inbox@pri.test", FRONTEND_URL="https://pri.test")
class ContactSubmissionTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_anyone_can_send_a_message_which_is_stored_and_emailed(self):
        response = self.client.post("/api/v1/contact/", message_data(), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        stored = ContactMessage.objects.get()
        self.assertEqual((stored.category, stored.status, stored.email), ("research", "new", "asha@example.org"))

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ["inbox@pri.test"])
        self.assertEqual(sent.reply_to, ["asha@example.org"])
        self.assertIn("Plus One study", sent.body)
        self.assertIn("https://pri.test/dashboard/inbox", sent.body)

    def test_a_filled_honeypot_is_accepted_but_nothing_is_kept_or_sent(self):
        response = self.client.post("/api/v1/contact/", message_data(website="http://spam.example"), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertFalse(ContactMessage.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_invalid_fields_are_refused(self):
        response = self.client.post(
            "/api/v1/contact/",
            message_data(email="not-an-email", category="sales", message="hi", name="  "),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data), {"email", "category", "message", "name"})
        self.assertFalse(ContactMessage.objects.exists())

    def test_a_mail_failure_keeps_the_message(self):
        with (
            mock.patch("apps.contact.services.EmailMessage.send", side_effect=OSError("smtp down")),
            self.assertLogs("apps.contact.services", "ERROR"),
        ):
            response = self.client.post("/api/v1/contact/", message_data(), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_one_sender_is_limited_to_five_messages_an_hour(self):
        for _ in range(5):
            self.assertEqual(self.client.post("/api/v1/contact/", message_data(), format="json").status_code, 201)
        self.assertEqual(self.client.post("/api/v1/contact/", message_data(), format="json").status_code, 429)
        self.assertEqual(
            self.client.post("/api/v1/contact/", message_data(email="other@example.org"), format="json").status_code,
            201,
        )

    def test_a_signed_in_token_is_ignored_rather_than_checked(self):
        response = self.client.post(
            "/api/v1/contact/", message_data(), format="json", HTTP_AUTHORIZATION="Bearer expired-or-bogus"
        )
        self.assertEqual(response.status_code, 201)


class ContactInboxTests(APITestCase):
    def setUp(self):
        self.editor = User.objects.create_user(username="editor", password="pw12345", role="editor")
        self.researcher = User.objects.create_user(username="researcher", password="pw12345", role="researcher")
        self.message = ContactMessage.objects.create(
            category="media", name="Ravi", email="ravi@example.org", message="Interview request for Friday."
        )

    def test_only_editors_and_admins_can_read_the_inbox(self):
        self.assertEqual(self.client.get("/api/v1/contact-messages/").status_code, 401)
        self.client.force_authenticate(self.researcher)
        self.assertEqual(self.client.get("/api/v1/contact-messages/").status_code, 403)
        self.client.force_authenticate(self.editor)
        listed = self.client.get("/api/v1/contact-messages/?status=new").data
        self.assertEqual([m["name"] for m in listed["results"]], ["Ravi"])

    def test_marking_handled_records_who_and_when_and_is_audited(self):
        self.client.force_authenticate(self.editor)
        response = self.client.patch(
            f"/api/v1/contact-messages/{self.message.pk}/", {"status": "handled"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["handled_by"], self.editor.pk)
        self.assertIsNotNone(response.data["handled_at"])
        entry = AuditLog.objects.get(module="contact")
        self.assertEqual(
            (entry.actor, entry.target, entry.metadata),
            (self.editor, f"contact_message:{self.message.pk}", {"from": "new", "to": "handled"}),
        )

        reopened = self.client.patch(
            f"/api/v1/contact-messages/{self.message.pk}/", {"status": "new"}, format="json"
        ).data
        self.assertEqual((reopened["handled_by"], reopened["handled_at"]), (None, None))

    def test_the_message_itself_cannot_be_edited(self):
        self.client.force_authenticate(self.editor)
        self.client.patch(
            f"/api/v1/contact-messages/{self.message.pk}/",
            {"message": "changed", "email": "x@example.org"},
            format="json",
        )
        self.message.refresh_from_db()
        self.assertEqual(
            (self.message.message, self.message.email), ("Interview request for Friday.", "ravi@example.org")
        )
        self.assertEqual(self.client.delete(f"/api/v1/contact-messages/{self.message.pk}/").status_code, 405)
