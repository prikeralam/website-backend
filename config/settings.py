"""
Django settings for the PRI backend project.
"""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")

# dev | staging | production. Anything other than "dev" turns on the deployed-environment guards below.
ENVIRONMENT = env("ENVIRONMENT", default="dev")
if ENVIRONMENT not in ("dev", "staging", "production"):
    raise ImproperlyConfigured(f"ENVIRONMENT must be dev, staging or production, got {ENVIRONMENT!r}")
DEPLOYED = ENVIRONMENT != "dev"

DEBUG = env.bool("DEBUG", default=True)
if DEPLOYED and DEBUG:
    raise ImproperlyConfigured(f"DEBUG must be False when ENVIRONMENT={ENVIRONMENT}")

if DEBUG:
    SECRET_KEY = env("SECRET_KEY", default="django-insecure-dev-key-change-me")
else:
    SECRET_KEY = env("SECRET_KEY", default="")
    if not SECRET_KEY:
        raise ImproperlyConfigured("SECRET_KEY must be set when DEBUG is False")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    "apps.accounts",
    "apps.taxonomy",
    "apps.content",
    "apps.projects",
    "apps.publications",
    "apps.datarepo",
    "apps.impact",
    "apps.contact",
    "apps.careers",
    "apps.events",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# runserver serves static files itself under DEBUG; WhiteNoise takes over for gunicorn deployments.
if not DEBUG:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    "default": env.db("DATABASE_URL", default="sqlite:///" + str(BASE_DIR / "db.sqlite3")),
}


# Cache: database-backed so throttle counters are shared by every gunicorn worker and instance.
# The table is created by apps/accounts/migrations/0002_cache_table.py.

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "pri_cache"},
}


# Custom user model (Module H)

AUTH_USER_MODEL = "accounts.User"


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static & media files

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# S3-compatible object storage (AWS S3 or DigitalOcean Spaces) — used when configured,
# falls back to local disk (Django's default FileSystemStorage) otherwise so local dev
# keeps working without real bucket credentials. Static files are served by WhiteNoise.
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
if AWS_STORAGE_BUCKET_NAME:
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
    AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default=None)
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default=None)
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}
elif DEPLOYED:
    # Uploads on an instance's local disk are lost on redeploy and never shared between environments.
    raise ImproperlyConfigured(f"AWS_STORAGE_BUCKET_NAME is required when ENVIRONMENT={ENVIRONMENT}")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Django REST Framework

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
    ),
    # Only views that opt in are throttled; `login` guards POST /api/v1/token/ (per username),
    # `password_reset` guards POST /api/v1/password-reset/ (per email); `contact` and
    # `contact_global` guard POST /api/v1/contact/ (per sender address, and in total).
    "DEFAULT_THROTTLE_RATES": {
        "login": "5/min",
        "password_reset": "5/hour",
        "contact": "5/hour",
        "contact_global": env("CONTACT_GLOBAL_RATE", default="200/hour"),
        # POST /api/v1/apply/: per applicant address, and in total.
        "application": "3/hour",
        "application_global": env("APPLICATION_GLOBAL_RATE", default="60/hour"),
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "SEARCH_PARAM": "q",
    # Disabled: DRF reserves `?format=` for content-negotiation (picking a renderer), which
    # collides with Module B's citation endpoint using `?format=bibtex|ris|apa` for its own
    # purpose (per PRD B). Nothing in this project relies on ?format=json-style negotiation.
    "URL_FORMAT_OVERRIDE": None,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "PRI Backend API",
    "DESCRIPTION": "v1 API for the PRI platform — see docs/api/*.md for the module-by-module contract.",
    "VERSION": "1.0.0",
    # Stable enum names for generated frontend clients: `status` is declared on several models.
    "ENUM_NAME_OVERRIDES": {
        "WorkflowStatusEnum": "apps.workflow.models.WorkflowStatus.choices",
        "AccessRequestStatusEnum": "apps.datarepo.models.AccessRequest.STATUS_CHOICES",
        "DatasetFormatEnum": "apps.datarepo.models.FORMAT_CHOICES",
        "ApplicationKindEnum": "apps.careers.models.APPLICATION_KIND_CHOICES",
        "ApplicationStatusEnum": "apps.careers.models.APPLICATION_STATUS_CHOICES",
        "EventKindEnum": "apps.events.models.EVENT_KIND_CHOICES",
        "EventModeEnum": "apps.events.models.EVENT_MODE_CHOICES",
    },
    "SERVE_INCLUDE_SCHEMA": False,
    # Explicit order (Swagger UI otherwise sorts tags alphabetically); mirrors docs/api/*.md.
    "TAGS": [
        {"name": "Module H — Users & Roles"},
        {"name": "Shared — Taxonomy"},
        {"name": "Module A — Content"},
        {"name": "Projects (Homepage)"},
        {"name": "Module B — Publications"},
        {"name": "Module C — Data Repository"},
        {"name": "Module D — Careers & Applications"},
        {"name": "Events & Campaigns"},
    ],
}


# Email (invites and password resets). Printed to the console in dev; deployed environments send
# over SMTP: Gmail for staging, Amazon SES for production, chosen by env values alone.

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend" if DEPLOYED
    else "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="PRI <no-reply@localhost>")
# Where contact-form messages are emailed (every category goes to this one address).
CONTACT_EMAIL = env("CONTACT_EMAIL", default="contact@priresearch.in")
# Where emailed links point: the frontend owns the /reset-password page.
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000").rstrip("/")


# CORS — allow the companion Next.js frontend's dev server

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"]
)


# HTTPS hardening — on for staging/production, off for local dev. Behind nginx, which sets
# X-Forwarded-Proto; /healthz/ stays reachable over plain HTTP for container health checks.

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=DEPLOYED)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=DEPLOYED)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=DEPLOYED)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000 if DEPLOYED else 0)
