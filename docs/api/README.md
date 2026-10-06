# PRI Backend — v1 API Contract

Cross-cutting conventions for the v1 API. Module-specific endpoint tables live in the sibling docs:

- [module-h-accounts-roles.md](module-h-accounts-roles.md) — Users, roles, audit log
- [module-a-content.md](module-a-content.md) — CMS content types
- [module-b-publications.md](module-b-publications.md) — Publication repository
- [module-c-data-repository.md](module-c-data-repository.md) — Datasets & dashboards
- [module-g-contact.md](module-g-contact.md) — Contact form and staff inbox

## Start here: frontend integration

- **Machine-readable contract:** [`openapi.yaml`](openapi.yaml) (OpenAPI 3.0, generated from the code, so it is the source of truth for request/response shapes). It is a snapshot; regenerate it after any endpoint change with `python manage.py spectacular --file docs/api/openapi.yaml --validate`. A running server also serves it at `/api/schema/`, with Swagger UI at `/api/docs/` and ReDoc at `/api/redoc/`. The module docs below explain intent, permissions and open decisions.
- **Base path:** `/api/v1/`. Send and receive JSON.
- **Auth:** `POST /api/v1/token/` with `{"username", "password"}` returns `{"access", "refresh"}`. Send `Authorization: Bearer <access>`. `POST /api/v1/token/refresh/` with `{"refresh"}` returns a new access token. `POST /api/v1/token/logout/` with `{"refresh"}` signs out by blacklisting that refresh token (a later refresh with it answers 401). Logins are throttled per username: the sixth attempt within a minute answers `429` (the limit is per username, not per IP, because the frontend proxies every login). Token lifetimes are SimpleJWT's defaults (access 5 minutes, refresh 1 day). There is no self-registration: admins create accounts (`POST /api/v1/users/`).
- **Anonymous read:** most `GET` endpoints work without a token and return published content only; see "Public-read endpoints" below.
- **Current user and role:** `GET /api/v1/users/me/role/` returns the signed-in user's `id`, `email` and `role` (`public`, `researcher`, `editor`, `fellow`, `admin`), for conditional rendering. `GET /api/v1/users/me/` returns the full profile; when its `must_change_password` is `true` (an admin set a temporary password), send the user to a change-password screen (`POST /api/v1/users/me/password/`).
- **Password emails:** invites and password resets link to `{FRONTEND_URL}/reset-password?uid=...&token=...`. The frontend owns that page and submits `POST /api/v1/password-reset/confirm/` with `uid`, `token` and `new_password`. See [module-h-accounts-roles.md](module-h-accounts-roles.md).
- **Lists:** paginated, `{"count", "next", "previous", "results"}`, 20 per page, `?page=N`. `?q=` searches publications and datasets. Filters per endpoint are in the module docs.
- **Errors:** `{"detail": "..."}` for auth, permission, not-found and most 4xx; validation errors are `{"field": ["message"]}`. `401` = no or bad token, `429` = too many sign-in attempts or reset requests, `403` = signed in but not allowed, `404` also covers objects the caller is not allowed to see. `422` is used by the dataset preview endpoints for unreadable files.
- **Workflow status** (`status` on every content type): `draft`, `in_review`, `approved`, `published`, `unpublished`. Anonymous callers only ever receive `published` objects.
- **CORS:** the API allows the origins in the `CORS_ALLOWED_ORIGINS` env var (default `http://localhost:3000`). The deployed frontend's origin must be added there for each environment.
- **Files:** `file` fields are URLs into object storage. Whether they are readable without a signature depends on the bucket policy.
- **Demo data:** on a local backend, `python manage.py seed_demo` loads the PRI prototype's content and one user per role (`demo_public`, `demo_researcher`, `demo_editor`, `demo_fellow`, `demo_admin`, password `demo-pass-123`). Dev only; it refuses to run in staging or production.
- **Not built yet:** Modules D (Fellowship), E (Media Watch), F (Donors), G (Forms).

Scope of this contract: **Modules A, B, C, H only.** Modules D (Fellowship), E (Media Watch), F (Donors), G (Forms) are each explicitly headed *"Future phase — not yet prioritized for build"* in their own PRDs (`docs/PRDs/D-*.md` … `G-*.md`) and are deliberately not drafted here — revisit when actually prioritized.

Every endpoint in these docs is cited to one of:
- **Built** — existing code, `file:line`.
- **PRD** — a specific PRD file:line under `docs/PRDs/`.
- **Proposed** — not fixed by any PRD; my proposal, flagged explicitly so it can be confirmed or changed rather than treated as settled.

## Versioning & base path

Every endpoint is mounted under `/api/v1/` (`config/urls.py`).

## Authentication

JWT via SimpleJWT — already built:
- `POST /api/v1/token/` — obtain access/refresh token pair. Throttled to 5 attempts a minute per username (`LoginRateThrottle`, `apps/accounts/throttles.py`; counters live in the database cache so every worker shares them); the sixth answers `429`. Built: `LoginView`, `apps/accounts/views.py`.
- `POST /api/v1/token/refresh/` — refresh an access token. Rejects blacklisted refresh tokens (`401`). Built: `config/urls.py`.
- `POST /api/v1/token/logout/` — `{"refresh"}`; blacklists the refresh token (SimpleJWT `token_blacklist`). `200` on success, `401` for an invalid or already-blacklisted token. Built: `LogoutView`, `apps/accounts/views.py`.

Accounts are provisioned by admins (`POST /api/v1/users/`, issue #38), with a temporary password or an emailed invite. No self-registration endpoint exists. Module H's PRD (`docs/PRDs/H-user-access-roles.md:43`) states only Donor/Visitor-tier accounts are meant to be self-service, and self-service donor registration is Module F's (Donor & Fundraising) territory, out of scope for this pass.

Password endpoints, all anonymous: `POST /api/v1/password-reset/` (`{"email"}`, always `204`, throttled to 5 an hour per email) and `POST /api/v1/password-reset/confirm/` (`{"uid", "token", "new_password"}`, `204`, or `400` for a used, expired or tampered link).

## Default permission model

`IsAuthenticated` is still the DRF-wide default (`config/settings.py`), so any endpoint not listed below requires a JWT. The exception is **public read** (issue #15): anonymous visitors may `GET` the endpoints in the table below, and only ever see what the "Who sees what" rule allows. Every write, and every action that acts on behalf of a user, still requires authentication.

### Public-read endpoints (no token needed)

| Endpoint | What anonymous callers get |
|---|---|
| `GET /content-blocks/`, `/testimonials/`, `/people/`, `/documents/`, `/projects/` (and `/{slug}/` or `/{id}/`) | published objects only |
| `GET /updates/latest/` | published items only (already the case) |
| `GET /publications/` (and `/{slug}/`, `/{slug}/citation/`, `/{slug}/download/`) | published publications with `visibility=public` only |
| `GET /datasets/` (and `/{slug}/`, `/{slug}/preview/table/`, `/{slug}/preview/map/`) | published datasets, `public` and `on_request` tiers. `internal_only` is a 404. An `on_request` dataset is listed but its `file` URL is omitted |
| `GET /datasets/{slug}/download/` | `public` tier only; `on_request` returns 403 until the signed-in user has an approved access request |
| `GET /dashboards/` (and `/{slug}/`) | published dashboards only |
| `GET /themes/` and `/themes/{id}/subthemes/` | all themes (reference data) |
| `POST /token/`, `POST /token/refresh/`, `POST /token/logout/` | login, refresh, sign-out |
| `POST /password-reset/`, `POST /password-reset/confirm/` | request a reset email, set a password from an emailed link |

Still authenticated: `users/me/`, `users/me/role/`, `users/me/password/`, every `users/` admin endpoint, `audit-log/`, `access-requests/`, `datasets/{slug}/request-access/`, every `transition/`, every write (`POST`/`PATCH`/`PUT`/`DELETE`). Anonymous callers get `401` on these.

### Who sees what (workflowed objects)

The same rule applies to every list and detail read, for every content type (A, B, C, Projects):

| Caller | Sees |
|---|---|
| anonymous, or signed in as `public` / `fellow` | `published` objects only |
| `researcher` | `published` objects plus their own drafts |
| `editor`, `admin` | everything |

Publications additionally hide `visibility=private` from everyone except staff and the creator. Datasets additionally hide `internal_only` from everyone except `researcher`/`editor`/`admin`. A hidden object returns `404`, not `403`, so its existence isn't revealed.

## Permission matrix (Module H, authoritative — see module-h doc)

Sourced directly from `apps/workflow/permissions.py` (`CONTRIBUTOR_ROLES = {researcher, editor, admin}`, `STAFF_ROLES = {editor, admin}`), the actual mechanism already shared by every workflowed content type. Documented once here; module docs reference it rather than re-deriving it.

| Action | public | researcher | editor | fellow | admin |
|---|---|---|---|---|---|
| Read published/public objects | ✅ | ✅ | ✅ | ✅ | ✅ |
| Create (draft) | ❌ | ✅ | ✅ | ❌ | ✅ |
| Edit own draft | ❌ | ✅ | ✅ | ❌ | ✅ |
| Edit any object past draft | ❌ | ❌ | ✅ | ❌ | ✅ |
| Transition draft → in_review (own object) | ❌ | ✅ | ✅ | ❌ | ✅ |
| Transition in_review → approved → published → unpublished | ❌ | ❌ | ✅ | ❌ | ✅ |
| Delete | ❌ | ❌ | ✅ | ❌ | ✅ |
| Grant/revoke roles | ❌ | ❌ | ❌ | ❌ | ✅ |
| List, create, edit, deactivate users; send password resets | ❌ | ❌ | ❌ | ❌ | ✅ |
| View and edit own profile, change own password | ✅ | ✅ | ✅ | ✅ | ✅ |
| View audit log | ❌ | ❌ | ❌ | ❌ | ✅ |

`fellow` has no permissions against A/B/C content today — per Module D's PRD, Fellow/Intern access is scoped to their *own* application status (Module D, out of scope here), not CMS/publication/dataset content.

## Pagination

Every list endpoint is paginated (`PageNumberPagination`, 20 per page, `?page=N`) with the standard DRF shape. The one exception is `GET /updates/latest/`, which returns a plain array capped by `?limit=` (default 20, max 100).

```json
{"count": 0, "next": null, "previous": null, "results": []}
```

## File storage

**Decision: S3-compatible object storage**, implemented in `config/settings.py`: it is used whenever `AWS_STORAGE_BUCKET_NAME` is set and local disk otherwise. Both Module C's PRD (`docs/PRDs/C-data-repository-dashboard-integration.md:41`) and Module E's PRD (`docs/PRDs/E-media-watch-rapid-response-module.md:33`) already assume "stored in S3/DigitalOcean Spaces (per project CLAUDE.md)," even though no CLAUDE.md or `config/settings.py` states this today — `config/settings.py:111-115` only configures local `MEDIA_ROOT`/`MEDIA_URL` (implicit `FileSystemStorage`), and `requirements.txt` has no `django-storages`/`boto3`.

Original target shape (now implemented, see `config/settings.py` for the real settings):

- Package: `django-storages[s3]` (uses `boto3` under the hood).
- Provider-agnostic via `AWS_S3_ENDPOINT_URL` so the same backend works for AWS S3 or DigitalOcean Spaces (PRD names both).
- `config/settings.py` target (Django 6.1 `STORAGES` dict form):
  ```python
  STORAGES = {
      "default": {"BACKEND": "storages.backends.s3.S3Storage"},
      "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
  }
  AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
  AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
  AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
  AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default=None)  # set for DO Spaces, unset for AWS S3
  AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default=None)
  ```
- Applies to every file field: `content_document.file` (already built, `apps/content/models.py:52`, currently local disk via Django's default storage), and the new `publications_publicationversion.file` and `datarepo_dataset.file` (both proposed below).
- Existing local `media/` files would need re-uploading to the bucket as part of the eventual cutover — a deployment concern for the follow-up implementation task, not addressed here.

## Shared Taxonomy — `Theme`

Built (`apps/taxonomy/`), beyond this contract's original scope: full CRUD, not the read-only endpoint originally planned.

| Method & Path | Auth | Filters | Notes |
|---|---|---|---|
| `GET /api/v1/themes/` | Public | `parent` (id), `top_level` (bool) | Read: anyone, including anonymous visitors. |
| `POST /api/v1/themes/` | Editor/Admin | — | Write: staff-only (`apps/taxonomy/permissions.py`'s `IsStaffOrReadOnly`) — taxonomy is shared reference data other modules FK to, not contributor-owned content. |
| `GET/PUT/PATCH/DELETE /api/v1/themes/{id}/` | Public (read) / Editor/Admin (write) | — | — |
| `GET/POST /api/v1/themes/{theme_id}/subthemes/` | Public (read) / Editor/Admin (write) | — | Nested CRUD scoped to one top-level theme's own sub-themes (`apps/taxonomy/views.py`'s `SubThemeViewSet`) — `parent` comes from the URL, not the request body, and is rejected/ignored if sent. `theme_id` must itself be a top-level theme (404 otherwise — can't nest a subtheme under a subtheme). |
| `GET/PUT/PATCH/DELETE /api/v1/themes/{theme_id}/subthemes/{id}/` | Public (read) / Editor/Admin (write) | — | — |

**Sub-themes:** `Theme.parent` is a nullable self-FK (`related_name="subthemes"`), capped at 2 levels — a sub-theme's own `parent` must itself be top-level (`Theme.clean()` / `ThemeSerializer.validate_parent`); a theme can't be its own parent. `(parent, name)` is unique together, so the same sub-theme name can recur under different top-level themes. The read serializer nests one level of `subthemes` (shallow — a subtheme's response doesn't itself list further children, since none can exist). A theme's sub-themes can be managed either via the flat `/themes/` endpoint (`parent` in the request body) or the nested `/themes/{theme_id}/subthemes/` endpoint (`parent` forced from the URL) — both operate on the same underlying `Theme` rows.

No PRD or the ERD names actual sub-theme values (only the 8 top-level themes are grounded in the live site, per `docs/erd/README.md:86-98`) — none are seeded; populate via either endpoint above once real sub-theme values are confirmed.

**One-to-many linkage from content:** `Publication.sub_theme` and `Dataset.sub_theme` each FK to exactly one `Theme`, and that `Theme` must itself be a sub-theme (`parent` set) — enforced in `PublicationSerializer.validate_sub_theme`/`DatasetSerializer.validate_sub_theme`, not at the DB level (a plain FK can't express "must have a non-null parent" as a constraint). One top-level theme's sub-themes can each be linked from many publications/datasets — a real one-to-many from `Theme` (as sub-theme) down to content, layered under the existing theme→subtheme one-to-many. Both `PublicationViewSet`/`DatasetViewSet` expose `?sub_theme=<id>` (exact) and `?theme=<id>` (via `sub_theme__parent_id`, to find everything under a top-level theme regardless of which sub-theme). `Dashboard.theme` is **not** changed by this rule — it still FKs directly to any `Theme` (typically top-level) — only Dataset/Publication were asked to require a sub-theme.

## Filtering convention

`DjangoFilterBackend` is already the DRF-wide default (`config/settings.py:129-131`). Today only `PublicationViewSet` (`apps/publications/views.py`) and `AuditLogListView` (`apps/accounts/views.py:53`) actually declare `filterset_fields` — the four Module A viewsets declare none despite the backend being active. Convention going forward: every list endpoint in this contract declares its filters explicitly (see each module doc).

## Error shape

Unmodified DRF defaults — no custom exception handler exists in code. Standard DRF error bodies (`{"detail": "..."}` or per-field validation dicts) apply throughout.
