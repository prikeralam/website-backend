from rest_framework.throttling import SimpleRateThrottle

from apps.accounts.throttles import LoginRateThrottle


class ApplicationEmailRateThrottle(LoginRateThrottle):
    """Limits applications per applicant address."""

    scope = "application"
    field = "email"


class ApplicationGlobalRateThrottle(SimpleRateThrottle):
    """A ceiling on all applications together; every one arrives from the frontend's server (see contact)."""

    scope = "application_global"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": "all"}
