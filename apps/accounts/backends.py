from django.contrib.auth.backends import ModelBackend

from .models import User


class EmailOrUsernameBackend(ModelBackend):
    """Signs in with an email address or a username.

    Visitors sign up with their email; staff accounts made earlier have usernames, which keep working. An email
    matches case-insensitively, and only if exactly one account uses it.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None or "@" not in username:
            return super().authenticate(request, username=username, password=password, **kwargs)
        matches = list(User._default_manager.filter(email__iexact=username.strip())[:2])
        if len(matches) != 1:
            # Hash anyway, so a missing or shared address takes as long as a wrong password.
            User().set_password(password)
            return None
        user = matches[0]
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
