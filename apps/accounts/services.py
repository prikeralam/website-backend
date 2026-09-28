"""User-management rules shared by the role, admin user and password endpoints."""
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.exceptions import ValidationError

from .models import AuditLog, Role, User


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
