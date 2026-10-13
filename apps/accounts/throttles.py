from rest_framework.throttling import SimpleRateThrottle


class LoginRateThrottle(SimpleRateThrottle):
    """Limits sign-in attempts per submitted username.

    Keyed on the username rather than the client IP: every login is proxied through the frontend's
    serverless functions, so all attempts arrive from a handful of shared IPs.
    """

    scope = "login"
    field = "username"

    def get_cache_key(self, request, view):
        value = request.data.get(self.field) if hasattr(request.data, "get") else None
        if not isinstance(value, str) or not value.strip():
            return None
        return self.cache_format % {"scope": self.scope, "ident": value.strip().lower()}


class PasswordResetRateThrottle(LoginRateThrottle):
    """Limits reset emails per submitted address, so the endpoint can't be used to flood an inbox."""

    scope = "password_reset"
    field = "email"


class RegisterRateThrottle(LoginRateThrottle):
    """Limits sign-ups per address, so the endpoint can't be used to flood an inbox."""

    scope = "register"
    field = "email"


class RegisterGlobalRateThrottle(SimpleRateThrottle):
    """A ceiling on all sign-ups together: they are posted by the frontend's server, which limits per visitor IP;
    this caps the total if that is bypassed."""

    scope = "register_global"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": "all"}


class VerificationResendRateThrottle(SimpleRateThrottle):
    """Limits confirmation emails per signed-in user."""

    scope = "verification_resend"

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}
