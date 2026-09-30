"""The image's HEALTHCHECK: GET /healthz/ on the local gunicorn, addressed to a host name Django accepts.

Requesting 127.0.0.1 directly fails wherever ALLOWED_HOSTS lists only the real name (every deployed host), because
Django answers a disallowed Host with 400.
"""

import os
import sys
import urllib.request


def health_host(allowed_hosts: str) -> str:
    """The first usable ALLOWED_HOSTS entry: ".example.org" also allows example.org itself; "*" allows anything."""
    for entry in allowed_hosts.split(","):
        host = entry.strip().lstrip(".")
        if host and host != "*":
            return host
    return "localhost"


def main() -> None:
    host = health_host(os.environ.get("ALLOWED_HOSTS", ""))
    request = urllib.request.Request("http://127.0.0.1:8000/healthz/", headers={"Host": host})
    try:
        urllib.request.urlopen(request, timeout=4)
    except Exception as error:
        print(f"unhealthy ({host}): {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
