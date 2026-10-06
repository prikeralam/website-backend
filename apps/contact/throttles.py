from rest_framework.throttling import SimpleRateThrottle

from apps.accounts.throttles import LoginRateThrottle


class ContactEmailRateThrottle(LoginRateThrottle):
    """Limits messages per sender address, so one visitor can't flood the inbox."""

    scope = "contact"
    field = "email"


class ContactGlobalRateThrottle(SimpleRateThrottle):
    """A ceiling on all contact messages together.

    Every message is posted by the frontend's server, so the backend can't tell visitors apart by
    IP; the frontend limits per visitor, and this caps the total if that is bypassed or overrun.
    """

    scope = "contact_global"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": "all"}
