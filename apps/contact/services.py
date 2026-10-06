import logging

from django.conf import settings
from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)


def notify_staff(message):
    """Emails a new contact message to PRI, with Reply-To set to the sender so staff can answer directly.

    The message is already saved; a mail failure is logged and never loses it (staff also see it in the
    dashboard inbox).
    """
    body = (
        f"New {message.get_category_display().lower()} message from the PRI website.\n\n"
        f"From: {message.name} <{message.email}>\n"
        f"Category: {message.get_category_display()}\n\n"
        f"{message.message}\n\n"
        f"Reply to this email to answer {message.name}. All messages: {settings.FRONTEND_URL}/dashboard/inbox"
    )
    email = EmailMessage(
        subject=f"[PRI contact] {message.get_category_display()}: {message.name}",
        body=body,
        to=[settings.CONTACT_EMAIL],
        reply_to=[message.email],
    )
    try:
        email.send()
    except Exception:
        logger.exception("Could not email contact message %s", message.pk)
