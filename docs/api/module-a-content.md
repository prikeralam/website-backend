# Module A — Content Management System

Source PRD: `docs/PRDs/A-content-management-system.md`. See [README.md](README.md) for auth, permission matrix, pagination, and file-storage conventions shared across all modules.

All four resources below share `apps/workflow`'s `WorkflowMixin` (status field) and the `/transition/` action (`apps/workflow/views.py`) — `draft → in_review → approved → published → unpublished`, role-gated per the [permission matrix](README.md#permission-matrix-module-h-authoritative--see-module-h-doc).

## Endpoints

| Method & Path | Auth | Filters | Status |
|---|---|---|---|
| `GET/POST /api/v1/content-blocks/` | Public read; write: contributor role | — | **Built** — `apps/content/views.py`, `apps/content/urls.py` |
| `GET /api/v1/content-blocks/{slug}/` | Public read | — | **Built** — PRD story 13 / `docs/PRDs/A-content-management-system.md:42`. Looked up by `slug`. |
| `GET/PATCH/DELETE /api/v1/content-blocks/{slug}/` | Public read; write: own draft or staff | — | **Built** |
| `POST /api/v1/content-blocks/{slug}/transition/` | Auth (role-gated) | — | **Built** — shared `WorkflowViewSetMixin` action |
| `GET/POST /api/v1/testimonials/` | Public read; write: contributor role | — | **Built** |
| `GET/POST /api/v1/people/` | Public read; write: contributor role | — | **Built** |
| `GET /api/v1/people/?group=` | Public read | `group` | **Built** — PRD story 8 (line 22). |
| `GET/POST /api/v1/documents/` | Public read; write: contributor role | — | **Built** |
| `GET /api/v1/documents/?document_type=&year=` | Public read | `document_type`, `year` | **Built** — PRD story 9 (line 23). |
| `GET /api/v1/updates/latest/?limit=&types=` | Public | `limit`, `types` | **Built** — PRD story 10 (lines 24, 46). Cross-type feed of most recently published content. |

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

## Uploaded images — `PersonProfile.photo`, `Project.image`

Both sit next to the existing URL fields (`photo_url`, `image_url`), so a photo can be uploaded from a computer or linked. When both are set, clients show the upload.

- Write with `multipart/form-data`. JPG, JPEG, PNG or WebP only, 5 MB at most (400 on the field otherwise).
- Read as the file's URL (presigned on S3, like document files), or `null` when there is no upload.
- Send `null` (JSON) or an empty value (multipart) to remove the upload. Omitting the field leaves it unchanged.
- Partners are `PersonProfile`s, so their logo upload is `photo`.

## SEO meta defaulting

PRD line 40: SEO title/description should default to a derived value (e.g. truncated body) if left blank at publish time. `seo_title`/`seo_description` fields already exist on `ContentBlock` (per ERD `content_contentblock`, `docs/erd/pri_platform_schema.sql:112-125`) but the defaulting logic itself isn't implemented — this is serializer/model `save()`-level logic to build, not a new endpoint.

## Not in scope for this module (per PRD's own Out of Scope, line 54-60)

- Publication Repository (Module B) — separate model.
- Data Repository (Module C) — separate model.
- Multi-language (EN/Malayalam) content storage strategy — explicitly unresolved in the PRD; flagged there as a pre-build decision if i18n is needed at launch, not resolved here either.
