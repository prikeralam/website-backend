from rest_framework.throttling import SimpleRateThrottle


class LoginRateThrottle(SimpleRateThrottle):
    """Limits sign-in attempts per submitted username.

    Keyed on the username rather than the client IP: every login is proxied through the frontend's
    serverless functions, so all attempts arrive from a handful of shared IPs.
    """

    scope = "login"

    def get_cache_key(self, request, view):
        username = request.data.get("username") if hasattr(request.data, "get") else None
        if not isinstance(username, str) or not username.strip():
            return None
        return self.cache_format % {"scope": self.scope, "ident": username.strip().lower()}
