# PRI Backend — v1 API Contract

Cross-cutting conventions for the v1 API. Module-specific endpoint tables live in the sibling docs:

- [module-h-accounts-roles.md](module-h-accounts-roles.md) — Users, roles, audit log
- [module-a-content.md](module-a-content.md) — CMS content types
- [module-b-publications.md](module-b-publications.md) — Publication repository
- [module-c-data-repository.md](module-c-data-repository.md) — Datasets & dashboards

Scope of this contract: **Modules A, B, C, H only.** Modules D (Fellowship), E (Media Watch), F (Donors), G (Forms) are each explicitly headed *"Future phase — not yet prioritized for build"* in their own PRDs (`docs/PRDs/D-*.md` … `G-*.md`) and are deliberately not drafted here — revisit when actually prioritized.

Every endpoint in these docs is cited to one of:
- **Built** — existing code, `file:line`.
- **PRD** — a specific PRD file:line under `docs/PRDs/`.
- **Proposed** — not fixed by any PRD; my proposal, flagged explicitly so it can be confirmed or changed rather than treated as settled.

## Versioning & base path

**Decision:** introduce `/api/v1/` as the base path for every endpoint below. `config/urls.py:11-19` is currently flat `/api/` with no versioning class configured in `REST_FRAMEWORK` (`config/settings.py:122-132`). Since the backend CLAUDE.md states "Nothing consumes this API yet," there is no compatibility cost to doing this now, before any frontend integration exists. Implementing this (updating `config/urls.py`'s `path("api/", ...)` prefixes to `path("api/v1/", ...)`) is follow-up work, not part of this doc pass.

## Authentication

JWT via SimpleJWT — already built:
- `POST /api/v1/token/` — obtain access/refresh token pair. Built: `config/urls.py:13`.
- `POST /api/v1/token/refresh/` — refresh an access token. Built: `config/urls.py:14`.

No self-registration endpoint exists anywhere in code today. Module H's PRD (`docs/PRDs/H-user-access-roles.md:43`) states only Donor/Visitor-tier accounts are meant to be self-service — Editor/Researcher/Admin accounts are provisioned internally. Self-service donor registration is Module F's (Donor & Fundraising) territory, out of scope for this pass. **Flagged as an open gap**, not silently filled: there is currently no way for *any* new account to be created via the API (only Django admin / `createsuperuser`).

## Default permission model

`IsAuthenticated` is the DRF-wide default (`config/settings.py:126-128`) — nothing is public/anonymous-read yet, matching the backend CLAUDE.md's explicit statement that this is deliberate until a frontend consumer exists. Every endpoint below is `IsAuthenticated` unless stated otherwise.

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
| View audit log | ❌ | ❌ | ❌ | ❌ | ✅ |

`fellow` has no permissions against A/B/C content today — per Module D's PRD, Fellow/Intern access is scoped to their *own* application status (Module D, out of scope here), not CMS/publication/dataset content.

## Pagination

**Open gap, flagged not fixed:** no `DEFAULT_PAGINATION_CLASS` is set (`config/settings.py`), so every list endpoint (built and proposed) is currently unpaginated. Recommend `rest_framework.pagination.PageNumberPagination` with the standard DRF shape:

```json
{"count": 0, "next": null, "previous": null, "results": []}
```

Not applied to code in this pass — implementation follow-up.

## File storage

**Decision: S3-compatible object storage**, replacing local disk. Both Module C's PRD (`docs/PRDs/C-data-repository-dashboard-integration.md:41`) and Module E's PRD (`docs/PRDs/E-media-watch-rapid-response-module.md:33`) already assume "stored in S3/DigitalOcean Spaces (per project CLAUDE.md)," even though no CLAUDE.md or `config/settings.py` states this today — `config/settings.py:111-115` only configures local `MEDIA_ROOT`/`MEDIA_URL` (implicit `FileSystemStorage`), and `requirements.txt` has no `django-storages`/`boto3`.

Target shape (documentation only — not applied to code in this pass):

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
| `GET /api/v1/themes/` | Auth | `parent` (id), `top_level` (bool) | Read: any authenticated user. |
| `POST /api/v1/themes/` | Editor/Admin | — | Write: staff-only (`apps/taxonomy/permissions.py`'s `IsStaffOrReadOnly`) — taxonomy is shared reference data other modules FK to, not contributor-owned content. |
| `GET/PUT/PATCH/DELETE /api/v1/themes/{id}/` | Auth (read) / Editor/Admin (write) | — | — |
| `GET/POST /api/v1/themes/{theme_id}/subthemes/` | Auth (read) / Editor/Admin (write) | — | Nested CRUD scoped to one top-level theme's own sub-themes (`apps/taxonomy/views.py`'s `SubThemeViewSet`) — `parent` comes from the URL, not the request body, and is rejected/ignored if sent. `theme_id` must itself be a top-level theme (404 otherwise — can't nest a subtheme under a subtheme). |
| `GET/PUT/PATCH/DELETE /api/v1/themes/{theme_id}/subthemes/{id}/` | Auth (read) / Editor/Admin (write) | — | — |

**Sub-themes:** `Theme.parent` is a nullable self-FK (`related_name="subthemes"`), capped at 2 levels — a sub-theme's own `parent` must itself be top-level (`Theme.clean()` / `ThemeSerializer.validate_parent`); a theme can't be its own parent. `(parent, name)` is unique together, so the same sub-theme name can recur under different top-level themes. The read serializer nests one level of `subthemes` (shallow — a subtheme's response doesn't itself list further children, since none can exist). A theme's sub-themes can be managed either via the flat `/themes/` endpoint (`parent` in the request body) or the nested `/themes/{theme_id}/subthemes/` endpoint (`parent` forced from the URL) — both operate on the same underlying `Theme` rows.

No PRD or the ERD names actual sub-theme values (only the 8 top-level themes are grounded in the live site, per `docs/erd/README.md:86-98`) — none are seeded; populate via either endpoint above once real sub-theme values are confirmed.

**One-to-many linkage from content:** `Publication.sub_theme` and `Dataset.sub_theme` each FK to exactly one `Theme`, and that `Theme` must itself be a sub-theme (`parent` set) — enforced in `PublicationSerializer.validate_sub_theme`/`DatasetSerializer.validate_sub_theme`, not at the DB level (a plain FK can't express "must have a non-null parent" as a constraint). One top-level theme's sub-themes can each be linked from many publications/datasets — a real one-to-many from `Theme` (as sub-theme) down to content, layered under the existing theme→subtheme one-to-many. Both `PublicationViewSet`/`DatasetViewSet` expose `?sub_theme=<id>` (exact) and `?theme=<id>` (via `sub_theme__parent_id`, to find everything under a top-level theme regardless of which sub-theme). `Dashboard.theme` is **not** changed by this rule — it still FKs directly to any `Theme` (typically top-level) — only Dataset/Publication were asked to require a sub-theme.

## Filtering convention

`DjangoFilterBackend` is already the DRF-wide default (`config/settings.py:129-131`). Today only `PublicationViewSet` (`apps/publications/views.py`) and `AuditLogListView` (`apps/accounts/views.py:53`) actually declare `filterset_fields` — the four Module A viewsets declare none despite the backend being active. Convention going forward: every list endpoint in this contract declares its filters explicitly (see each module doc).

## Error shape

Unmodified DRF defaults — no custom exception handler exists in code. Standard DRF error bodies (`{"detail": "..."}` or per-field validation dicts) apply throughout.
