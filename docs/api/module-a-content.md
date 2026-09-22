# Module A — Content Management System

Source PRD: `docs/PRDs/A-content-management-system.md`. See [README.md](README.md) for auth, permission matrix, pagination, and file-storage conventions shared across all modules.

All four resources below share `apps/workflow`'s `WorkflowMixin` (status field) and the `/transition/` action (`apps/workflow/views.py`) — `draft → in_review → approved → published → unpublished`, role-gated per the [permission matrix](README.md#permission-matrix-module-h-authoritative--see-module-h-doc).

## Endpoints

| Method & Path | Auth | Filters | Status |
|---|---|---|---|
| `GET/POST /api/v1/content-blocks/` | Auth (write: contributor role) | — | **Built** — `apps/content/views.py`, `apps/content/urls.py` |
| `GET /api/v1/content-blocks/{slug}/` | Auth | — | **To build** — PRD story 13 / `docs/PRDs/A-content-management-system.md:42`. Router currently looks up by `pk`; needs `lookup_field="slug"`. |
| `GET/PATCH/DELETE /api/v1/content-blocks/{pk}/` | Auth (own draft or staff) | — | **Built** |
| `POST /api/v1/content-blocks/{pk}/transition/` | Auth (role-gated) | — | **Built** — shared `WorkflowViewSetMixin` action |
| `GET/POST /api/v1/testimonials/` | Auth | — | **Built** |
| `GET/POST /api/v1/people/` | Auth | — | **Built** |
| `GET /api/v1/people/?group=` | Auth | `group` | **To build** — PRD story 8 (line 22). Field exists (`PersonProfile.group`); needs `filterset_fields = ["group"]` added to the viewset. |
| `GET/POST /api/v1/documents/` | Auth | — | **Built** |
| `GET /api/v1/documents/?type=&year=` | Auth | `document_type`, `year` | **To build** — PRD story 9 (line 23). Fields don't exist in code yet; ERD flags them explicitly not-yet-built (`docs/erd/README.md:77`, `docs/erd/pri_platform_schema.sql:164-165`). |
| `GET /api/v1/updates/latest/?limit=&types=` | Auth | `limit`, `types` | **To build** — PRD story 10 (lines 24, 46). Cross-type feed of most recently published content. |

Every content-type resource also gets `POST /{pk}/transition/` (built, shared action) — omitted from the table above for brevity, one row per resource type.

## `GET /updates/latest/` — design note

Not built. PRD wants results "ordered by publish date" across content types. **Dependency gap:** `WorkflowMixin` (`apps/workflow/models.py:13-23`) has `updated_at` (auto-updates on every save) but no `published_at` — so "publish date" has no dedicated field to order by today. Two options, neither implemented here:
1. Add a `published_at` field, set once on the `draft→...→published` transition (in `WorkflowViewSetMixin.transition`, `apps/workflow/views.py`), left `null` otherwise.
2. Fall back to `updated_at` at the time status becomes `published`, accepting that a later unrelated edit would incorrectly bump ordering.

Recommend option 1 (a dedicated `published_at`) since option 2's imprecision would directly corrupt the Homepage's "Latest Updates" ordering — flagged for confirmation before building.

## Fields to add — `Document`

Per ERD (`docs/erd/pri_platform_schema.sql:158-172`), `content_document` needs two columns not yet in `apps/content/models.py`:
- `document_type` — `VARCHAR(50)`, e.g. "Annual Report", "Strategic Plan".
- `year` — nullable integer.

Both exist solely to support the `?type=&year=` filter PRD story 9 asks for.

## SEO meta defaulting

PRD line 40: SEO title/description should default to a derived value (e.g. truncated body) if left blank at publish time. `seo_title`/`seo_description` fields already exist on `ContentBlock` (per ERD `content_contentblock`, `docs/erd/pri_platform_schema.sql:112-125`) but the defaulting logic itself isn't implemented — this is serializer/model `save()`-level logic to build, not a new endpoint.

## Not in scope for this module (per PRD's own Out of Scope, line 54-60)

- Publication Repository (Module B) — separate model.
- Data Repository (Module C) — separate model.
- Multi-language (EN/Malayalam) content storage strategy — explicitly unresolved in the PRD; flagged there as a pre-build decision if i18n is needed at launch, not resolved here either.
