import logging

from django.conf import settings
from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)


def notify_staff(application):
    """Tells PRI a new application arrived. The files stay in storage and open from the dashboard, not the email.

    The application is already saved; a mail failure is logged and never loses it.
    """
    applying_for = application.job.title if application.job else application.get_kind_display()
    body = (
        f"New application from the PRI website.\n\n"
        f"From: {application.full_name} <{application.email}>\n"
        f"Applying for: {applying_for}\n\n"
        f"The CV and statement of purpose are in the dashboard: {settings.FRONTEND_URL}/dashboard/applications\n"
        f"Reply to this email to answer {application.full_name}."
    )
    email = EmailMessage(
        subject=f"[PRI application] {applying_for}: {application.full_name}",
        body=body,
        to=[settings.CONTACT_EMAIL],
        reply_to=[application.email],
    )
    try:
        email.send()
    except Exception:
        logger.exception("Could not email application %s", application.pk)
