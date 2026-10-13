"""User-management rules shared by the role, admin user, password and sign-up endpoints."""

import re

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.exceptions import ValidationError

from .models import AuditLog, Role, User
from .tokens import email_verification_token

# Where a confirmation link may send the visitor back to: a path on this site, e.g. "/data/plus-one-batch-size".
SAFE_NEXT = re.compile(r"^/(?!/)[A-Za-z0-9/_\-]{0,200}$")


def audit(actor, action, user, **metadata):
    AuditLog.objects.create(actor=actor, module="accounts", action=action, target=f"user:{user.pk}", metadata=metadata)


def guard_admin_lockout(actor, target):
    """Refuses a change that takes `target` out of the active admins, if it would lock the admins out.

    Call before demoting or deactivating. An admin may not do either to themselves, and the last
    active admin can't be removed by any path.
    """
    if target.pk == actor.pk:
        raise ValidationError({"detail": "You can't remove your own admin access. Ask another admin."})
    other_admins = User.objects.filter(role=Role.ADMIN, is_active=True).exclude(pk=target.pk)
    if target.role == Role.ADMIN and target.is_active and not other_admins.exists():
        raise ValidationError({"detail": "This is the last active admin."})


def password_link(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"


def send_password_email(user):
    """Emails a set-password link: an invite if the user has never had a password, a reset otherwise.

    Both links finish at POST /api/v1/password-reset/confirm/. A link stops working once the
    password changes, because the token is derived from the current password hash.
    """
    link = password_link(user)
    if user.has_usable_password():
        subject = "Reset your PRI password"
        body = (
            f"Hello {user.get_short_name() or user.username},\n\n"
            f"Use this link to choose a new password for your PRI account ({user.username}):\n\n{link}\n\n"
            "If you didn't ask for this, you can ignore this email; your password stays the same."
        )
    else:
        subject = "You've been invited to PRI"
        body = (
            f"Hello {user.get_short_name() or user.username},\n\n"
            f"An account has been created for you on the PRI platform. Your username is {user.username}.\n"
            f"Use this link to set your password and sign in:\n\n{link}"
        )
    send_mail(subject, body, None, [user.email])


def safe_next(path):
    """`path` if it is a plain path on this site, else empty; it goes into a link, so nothing else may pass."""
    return path if isinstance(path, str) and SAFE_NEXT.match(path) else ""


def verification_link(user, next_path=""):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    link = f"{settings.FRONTEND_URL}/verify-email?uid={uid}&token={token}"
    next_path = safe_next(next_path)
    return f"{link}&next={next_path}" if next_path else link


def send_verification_email(user, next_path=""):
    """Asks a new visitor to confirm their address; downloads open once they do."""
    body = (
        f"Hello {user.get_short_name() or user.email},\n\n"
        "Thank you for creating an account with the Policy and Research Initiative.\n"
        f"Please confirm your email address to start downloading datasets:\n\n{verification_link(user, next_path)}\n\n"
        "If you didn't create this account, you can ignore this email."
    )
    send_mail("Confirm your email for PRI", body, None, [user.email])


def send_existing_account_email(user):
    """Sent when someone signs up with an address that already has an account, instead of saying so on the page,
    which would tell anyone which addresses are registered."""
    body = (
        f"Hello {user.get_short_name() or user.email},\n\n"
        "Someone, probably you, tried to create a PRI account with this email address, but you already have one.\n"
        f"Sign in with this email address, or choose a new password here:\n\n{password_link(user)}\n\n"
        "If this wasn't you, you can ignore this email."
    )
    send_mail("You already have a PRI account", body, None, [user.email])
