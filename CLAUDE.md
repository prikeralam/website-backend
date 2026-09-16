# PRI Backend

## What this is

Django + Django REST Framework backend for **PRI** (Policy and Research Initiative). It serves everything on the org's digital platform except the Data Repository: a CMS for content (content blocks, testimonials, team/people profiles, documents), Projects, Research Publications, and a Users/Roles/Audit-log system (Module H).

It deliberately does **not** own datasets or CKAN integration — that "Data Repository & Dashboard Integration" module (Module C) is CKAN-backed and lives in the separate Next.js frontend repo (`Website`), with its own Prisma/Postgres thin API layer in front of CKAN. This backend is not aware of that system and should not duplicate it.

Nothing consumes this API yet. It is built ahead of a future integration pass with a Next.js frontend — kept clean and correct, not speculatively extensible beyond what's specified here.

## Tech stack

- **Framework:** Django + Django REST Framework
- **Auth:** SimpleJWT (`djangorestframework-simplejwt`) — `/api/token/`, `/api/token/refresh/`
- **Database:** PostgreSQL, run locally via Docker Compose
- **Config:** `django-environ`, loaded from `.env` (gitignored; see `.env.example` for the shape)
- **Filtering:** `django-filter`, wired as DRF's default filter backend
- **CORS:** `django-cors-headers`, allowing `http://localhost:3000` (the companion Next.js frontend's dev port)

## Running locally

```bash
# 1. Create and activate a virtualenv
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate    # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy env file and adjust if needed
cp .env.example .env

# 4. Start Postgres
docker compose up -d

# 5. Migrate and run
python manage.py migrate
python manage.py runserver
```

Admin site is at `/admin/`. API is mounted under `/api/`.

## Architectural decisions

### Shared workflow mixin

Every content type (`ContentBlock`, `Testimonial`, `PersonProfile`, `Document`, `Project`, `Publication`) inherits an abstract `WorkflowMixin` (`apps/workflow/models.py`) carrying a `status` field with five states:

```
draft -> in_review -> approved -> published -> unpublished
```

Transitions are role-gated via `apps/workflow/permissions.py` and a shared `transition` action (`apps/workflow/views.py`) every content-type ViewSet includes:

- **`draft -> in_review`**: allowed for the object's own `created_by` if their role is `researcher`, `editor`, or `admin` (a "contributor" role) — OR for any `editor`/`admin` regardless of ownership.
- **Any other transition** (`in_review -> approved`, `approved -> published`, `published -> unpublished`, etc.): allowed only for `editor` or `admin`.
- Every successful transition writes an `AuditLog` row (`apps.accounts.models.AuditLog`) recording actor, module, action (`status_transition`), and target.

Creation (`POST`) is allowed for contributor roles (`researcher`, `editor`, `admin`). Editing a `draft` object (`PATCH`/`PUT`) is allowed for its own creator (any contributor role) or for `editor`/`admin`.

### Role enum mirrors the frontend's mock-auth roles

The 5-role enum (`public`, `researcher`, `editor`, `fellow`, `admin`) in `apps/accounts/models.py` deliberately uses the same string values as the companion Next.js frontend project's own mock-auth `Role` type (`app/_lib/mockAuth.ts` in the `Website` repo), so the two systems don't need a translation layer when they're eventually wired together.

**Note:** `public` is used (not `donor`), even though it represents a donor/visitor account — again, purely to match the frontend's existing enum value.

### Datasets/CKAN out of scope

This backend does not model datasets, dashboards, or anything CKAN-related. That is Module C, owned entirely by the frontend repo's own API layer (`app/api/datasets/*`, Prisma) sitting in front of a separate `pri-ckan` CKAN deployment. Do not add dataset models here.

### No frontend integration yet

This is a backend-only build. All endpoints require authentication by default (`IsAuthenticated`); nothing is exposed as public/anonymous-read yet since there is no consuming frontend. A future pass will wire a Next.js frontend to these APIs and revisit which endpoints should allow public read access.

## Changelog

- **2026-09-16** — Initial project setup: gitignore, README, CLAUDE.md, scaffolded Django+DRF project (`config/`, `apps/workflow|accounts|content|projects|publications`), Postgres via Docker Compose on port 5435, JWT auth, role-gated workflow mixin, audit log. See README for run instructions.
