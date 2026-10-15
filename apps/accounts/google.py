"""Checks the ID token that Google Identity Services hands the browser after "Sign in with Google"."""

import jwt
from django.conf import settings

GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ["accounts.google.com", "https://accounts.google.com"]

# Fetches and caches Google's signing keys (they rotate, and the client refetches when it meets an unknown key id).
_keys = jwt.PyJWKClient(GOOGLE_CERTS_URL, cache_keys=True, lifespan=3600, timeout=10)


class InvalidGoogleToken(Exception):
    pass


class GoogleUnavailable(Exception):
    """Google's keys couldn't be fetched; the token may be fine, so this is an outage, not a refusal."""


def verify_google_credential(credential):
    """Returns the token's claims if Google signed it for this site's client and the address is verified.

    Raises InvalidGoogleToken for anything else: a bad signature, another site's client ID, an expired token,
    or an address Google hasn't verified. Raises GoogleUnavailable when Google's keys can't be fetched.
    """
    try:
        key = _keys.get_signing_key_from_jwt(credential)
    except jwt.PyJWKClientConnectionError as error:
        raise GoogleUnavailable(str(error)) from error
    except jwt.PyJWTError as error:
        raise InvalidGoogleToken(str(error)) from error
    try:
        claims = jwt.decode(
            credential,
            key.key,
            algorithms=["RS256"],
            audience=settings.GOOGLE_CLIENT_ID,
            issuer=GOOGLE_ISSUERS,
            options={"require": ["exp", "iat", "aud", "iss", "sub", "email"]},
            leeway=30,
        )
    except jwt.PyJWTError as error:
        raise InvalidGoogleToken(str(error)) from error
    if claims.get("email_verified") is not True:
        raise InvalidGoogleToken("Google hasn't verified this address")
    return claims
