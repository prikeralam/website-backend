# PRI Backend

## What this is

Django + Django REST Framework backend for **PRI** (Policy and Research Initiative). It serves everything on the org's digital platform: a CMS for content (content blocks, testimonials, team/people profiles, documents), Projects, Research Publications (Module B), the Data Repository & Dashboards (Module C — datasets, dashboards, access requests), a shared Theme taxonomy, and a Users/Roles/Audit-log system (Module H). Modules D (Fellowship), E (Media Watch), F (Donors), G (Forms) are not built — each is still headed "Future phase" in its own PRD.

The full v1 API contract for the built modules (A/B/C/H) — endpoints, permission rules, filters, and what's cited to which PRD line vs. proposed — lives in `docs/api/*.md`, with a generated `docs/api/openapi.yaml` for frontend clients (regenerate it whenever an endpoint changes: `python manage.py spectacular --file docs/api/openapi.yaml --validate`); treat it as the source of truth for what the API should expose, ahead of `apps/*/views.py` for "why" a given endpoint exists.

Nothing consumes this API yet. It is built ahead of a future integration pass with a Next.js frontend — kept clean and correct, not speculatively extensible beyond what's specified here.

## Tech stack

- **Framework:** Django + Django REST Framework, API versioned under `/api/v1/`
- **Auth:** SimpleJWT (`djangorestframework-simplejwt`) — `/api/v1/token/`, `/api/v1/token/refresh/`
- **Database:** PostgreSQL, run locally via Docker Compose
- **Config:** `django-environ`, loaded from `.env` (gitignored; see `.env.example` for the shape)
- **Filtering:** `django-filter`, wired as DRF's default filter backend; `?q=` search (`SEARCH_PARAM`) on publications/datasets. DRF's `?format=` content-negotiation override is disabled (`URL_FORMAT_OVERRIDE: None`) since it collided with Module B's citation endpoint's own `?format=bibtex|ris|apa` param.
- **File storage:** local disk (`FileSystemStorage`) unless `AWS_STORAGE_BUCKET_NAME` is set in `.env`, in which case `django-storages`' `S3Storage` is used instead (works for AWS S3 or DigitalOcean Spaces via `AWS_S3_ENDPOINT_URL`) — see `config/settings.py`.
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
python manage.py seed_demo   # optional: demo users + the PRI prototype's content (dev only)
python manage.py runserver
```

Admin site is at `/admin/`. API is mounted under `/api/v1/`.

## Architectural decisions

### Shared workflow mixin

Every content type (`ContentBlock`, `Testimonial`, `PersonProfile`, `Document`, `Project`, `Publication`, `Dataset`, `Dashboard`) inherits an abstract `WorkflowMixin` (`apps/workflow/models.py`) carrying a `status` field with five states, plus a `published_at` timestamp set the first time an object reaches `published` (used to order Module A's `/updates/latest/` feed):

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

### Module C (datasets/dashboards) is native Django, not CKAN

Module C was originally planned to be CKAN-backed (`app/api/datasets/*` in the `Website` repo, per the PRD's 2026-09-15 amendment), then reversed back to native Django (2026-09-19 amendment) and built here as `apps/datarepo` (2026-09-21): `Dataset`, `Dashboard`, `AccessRequest` models, three-tier visibility (`public`/`on_request`/`internal_only`, enforced in `apps/datarepo/permissions.py` — `internal_only` is genuinely invisible to non-`researcher`/`editor`/`admin` roles, not just download-gated), an `AccessRequest` approve/deny workflow (`GET`/`PATCH /api/v1/access-requests/...`), and table-preview (`GET /datasets/{slug}/preview/table/` — `csv`, `parquet` via `pyarrow`, and `zip` by its first CSV member; parsers live in `apps/datarepo/previews.py`) rather than raw file downloads. Map preview (`GET /datasets/{slug}/preview/map/`) serves `geojson` datasets (a fourth `format` choice) as-is for the frontend to render, capped at 10 MB; shapefile-in-zip and GeoParquet are not supported (parsing in `apps/datarepo/geo.py`). `pri-ckan` is decommissioned per the amendment; it isn't referenced by this backend.

### Deployment

`feat/*` -> `dev` -> `staging` -> `main`, deployed by GitHub Actions on merge to `staging` and `main` (full description in `.github/CONTRIBUTING.md` section 5). Production promotes the image already built on staging when the tree matches, pauses for approval in the `production` Environment, and snapshots RDS before deploying. `ENVIRONMENT` (`dev`/`staging`/`production`) gates settings: deployed environments refuse `DEBUG=True` or a missing bucket. Branch rulesets are not enforced yet (GitHub Free, private repo), so never push directly to `dev`, `staging` or `main`.

### Public read for the frontend

`IsAuthenticated` is still the DRF default, so anything not listed in `docs/api/README.md` ("Public-read endpoints") needs a JWT. Anonymous visitors may `GET` content, projects, publications, datasets, dashboards, themes and the updates feed, subject to one shared rule (`visible_workflow_objects` in `apps/workflow/permissions.py`, applied by `WorkflowViewSetMixin.get_queryset`): anonymous/`public`/`fellow` callers see `published` objects only, `researcher`s also see their own drafts, `editor`/`admin` see everything. Publications also hide `visibility=private`, datasets hide `internal_only`, and an `on_request` dataset's `file` URL is dropped from responses to anyone `/download/` would refuse. Writes and every `transition/` action still require a token. Leak boundaries are tested in `apps/workflow/tests.py`.

## Changelog

- **2026-09-29** — Staging moved from `15-206-144-63.sslip.io` to the real subdomain `api-staging.priresearch.in` (A record at GoDaddy, where `priresearch.in` is registered; new certbot certificate on the host). `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` and `SERVER_NAME` now use it, and `FRONTEND_URL`/`CORS_ALLOWED_ORIGINS` point at the frontend's new `https://staging.priresearch.in`, so invite and reset emails link there. Applied on the host and in the `staging` Environment's `APP_ENV_FILE` secret, whose content is now also kept locally at `~/.pri-deploy/backend-staging.env`. The sslip.io name is no longer served.
- **2026-09-28** — Admin user management over the API (issue #38), so the frontend can run an admin UI without Django admin. Admins list and search users, create them with a temporary password (forced change on first sign-in via `must_change_password`) or an emailed invite, edit contact details, deactivate/reactivate (no delete, because content keeps its author), and send password resets. Every user gets `/users/me/`, a password change, and a forgot-password flow. The role now drives Django admin rights on every save (`User.save()`; migration `0003` promotes existing superusers to `admin`), and an admin can't demote or deactivate themselves or the last active admin. Deactivation relies on SimpleJWT's built-in `is_active` check rather than blacklisting tokens. Email is env-configured: console in dev, Gmail SMTP on staging, SES in production. Contract in `docs/api/module-h-accounts-roles.md`.

- **2026-09-28** — Provisioned staging on AWS (issue #7, staging half) as CloudFormation in `deploy/aws/`, documented in `docs/deploy/aws-provisioning.md`. One `t3.micro` Ubuntu host in ap-south-1 runs the existing staging compose stack at `15-206-144-63.sslip.io`, a free wildcard-DNS hostname, so Let's Encrypt works without a domain. The private `pri-staging-<account>` bucket is reached through the instance role, so no static AWS keys live in the env file. An account budget emails at 50/80/100% of $20/month gross spend (credits excluded, so it warns before the $100 credit runs out). Production (EC2 + RDS + prod bucket) is deliberately deferred to save credits.
- **2026-09-26** — `seed_demo` now uses the real material PRI supplied instead of placeholders where it exists: patrons and 10 of 13 executive council members get `photo_url`s pointing at the frontend's `/people/{patrons,executive}/` photos (Abubakr T, Anwar Naha and Abdul Muhaimin Kakkiya have none yet), and the Annual Report 2025–26 document is the real PDF, now kept in `apps/accounts/management/commands/seed_files/` (the frontend no longer serves it from `public/`). Files are attached only when a document has none, so an already-seeded database keeps its placeholder until the row is deleted.
- **2026-09-26** — Closed the two sign-in gaps the frontend's security review found (#31). Logins (`POST /api/v1/token/`) are now throttled to 5 a minute **per submitted username**, not per IP, because the Next.js frontend proxies every login from shared serverless IPs; the counters live in a new database cache (`CACHES` → `pri_cache`, created by migration `accounts.0002_cache_table`, so deploys need no extra step), since the default per-process cache would give each gunicorn worker its own limit. Sign-out is real: SimpleJWT's `token_blacklist` app is installed and `POST /api/v1/token/logout/` blacklists a refresh token, after which refreshing with it answers 401. Refresh-token rotation stays off so the refresh response the frontend reads is unchanged. `flushexpiredtokens` can be scheduled later to prune the blacklist tables.
- **2026-09-25** — Added `python manage.py seed_demo` so a frontend has real data to render. It loads the content of the PRI website prototype (pages, the 7-person team, patrons, executive council, advisory body, partners, three projects, the four data stories, two annual reports and two dashboards, plus datasets built only from figures quoted in those stories) and one demo user per role (`demo_<role>`, password `demo-pass-123`). A few extra draft, private and gated rows exist only to exercise the visibility rules, and where the prototype says "to be supplied" the seed does too. It is idempotent and refuses to run unless `ENVIRONMENT=dev`, since it creates accounts with a known password.
- **2026-09-25** — Prepared the API contract for the frontend repo: committed a validated OpenAPI 3.0 schema (`docs/api/openapi.yaml`, generated from the code) and added a "Start here: frontend integration" section to `docs/api/README.md` covering the JWT flow, pagination, error shapes, anonymous read, CORS and workflow statuses. Refreshed statements that had gone stale since the contract was first drafted (endpoints marked "To build" that are built, pagination and file storage described as open gaps, `/api/v1/` as a follow-up). Gave the shared `status` enums stable names in the schema so generated clients get one `WorkflowStatusEnum`, and fixed the sub-theme schema warning.
- **2026-09-25** — Opened the API to anonymous read for the frontend integration (issue #15). Before this, every list endpoint returned every object, drafts included, to any signed-in user, so making reads public meant fixing that first: one shared visibility rule now decides what each caller sees (published only for anonymous, `public` and `fellow`; own drafts too for researchers; everything for editors and admins), and `on_request` dataset file URLs no longer leak through list and detail responses. Writes and workflow transitions still need a token. Existing test fixtures now publish their objects, and `apps/workflow/tests.py` covers the leak boundaries for each role and content type.
- **2026-09-25** — Map preview now works (issue #10): added `geojson` as a `Dataset.format` choice (migration `0004`) and made `preview/map/` return the parsed GeoJSON, so the frontend can render it without a GIS dependency on the backend. GeoJSON only, by decision: shapefile-in-zip and GeoParquet would need a GIS library and stay out until a dataset needs them. Non-GeoJSON datasets and malformed files return `422`, files over 10 MB return `413`, and the three-tier visibility rules apply unchanged.
- **2026-09-25** — Table preview now works for `parquet` and `zip` datasets (issue #9), so every committed dataset format previews instead of returning `501`. Added `pyarrow` (approved for this) to read parquet a page at a time without loading the whole file; zip previews stream the first CSV member with the stdlib. A corrupt file or a zip with no CSV returns `422` rather than a 500. Preview parsing moved out of the view into `apps/datarepo/previews.py`.
- **2026-09-25** — Documented the CI/CD pipeline that landed in PRs #17-#21: `.github/CONTRIBUTING.md` section 5 now lists each workflow (CI, PR guard, deploy staging, deploy production, hotfix backport), the tested-image promotion from staging to prod, the release flow with merge methods (squash into `dev`, merge commits for promotions), and the per-Environment secrets. Records that branch rulesets are not applied because GitHub Free can't protect private-repo branches (issue #6), so the workflow is followed by convention: CI and `pr-guard` run but do not block merges. Added `scripts/setup-github-protection.sh` to apply Environments and rulesets once the plan or visibility allows. README gained a deploy section; `.github/git-workflow.md` now points to CONTRIBUTING.md.
- **2026-09-21** — Drafted the v1 API contract (`docs/api/*.md`, one doc per module A/B/C/H plus a shared README of conventions) grounded in the ERD and the 8 PRDs (copied into `docs/PRDs/`), then implemented it: versioned every endpoint under `/api/v1/`; added `apps/taxonomy` (shared `Theme` lookup, seeded with the canonical 8 values, FK'd from `Publication` and `Dataset`); added `published_at` to `WorkflowMixin` and wired `GET /updates/latest/` (Module A's cross-type feed); extended `Document` (`document_type`/`year` filters), `Publication` (versioning via `PublicationVersion`, `visibility` toggle, `external_id`, `tags`, 7-value `format`, citation export at `/citation/?format=bibtex|ris|apa`); and built `apps/datarepo` from scratch for Module C (`Dataset`/`Dashboard`/`AccessRequest`, three-tier visibility enforcement, CSV table preview, access-request review queue). Added conditional S3-compatible file storage (`django-storages`, on when `AWS_STORAGE_BUCKET_NAME` is set, local disk otherwise) and DRF pagination/search defaults. 34 new tests across `apps/content`, `apps/publications`, `apps/datarepo`, weighted toward each PRD's own stated highest-risk guarantee (workflow-transition permissions for A, the private-publication visibility toggle for B, the three-tier dataset visibility leak check for C). Modules D/E/F/G remain undrafted and unbuilt — each is still "Future phase" in its own PRD.
- **2026-09-17** — Designed a full-project ER schema (`docs/erd/pri_platform_schema.sql`, `docs/erd/README.md`) covering all 8 backend modules (A–H), not just what's built, so the remaining modules (C–H) have an agreed target data model before implementation starts. Decided Module C (Data Repository & Dashboards) will be built natively in this Django backend instead of CKAN — dropping the CKAN/Prisma-thin-layer plan from the PRD's 2026-09-15 amendment; see the updated "Module C is native Django, not CKAN" section above.
- **2026-09-16** — Initial project setup: gitignore, README, CLAUDE.md, scaffolded Django+DRF project (`config/`, `apps/workflow|accounts|content|projects|publications`), Postgres via Docker Compose on port 5435, JWT auth, role-gated workflow mixin, audit log. See README for run instructions.

## Agent skills

### Issue tracker

GitHub issues tracked via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical 5-role triage vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout (`CONTEXT.md` and `docs/adr/` at repo root). See `docs/agents/domain.md`.
