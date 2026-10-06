# Module C — Data Repository & Dashboards

Source PRD: `docs/PRDs/C-data-repository-dashboard-integration.md`. See [README.md](README.md) for auth, permission matrix, pagination, and file-storage conventions shared across all modules.

**Status: entirely new.** No `apps/datarepo` exists yet. Per the PRD's 2026-09-19 amendment (lines 91-113), this module is canonical as a bespoke Django + DRF app — the original (pre-CKAN) Implementation Decisions section is the source of truth, built with `apps.workflow`'s `WorkflowMixin`/`CanSubmitDraft`/`CanTransitionStatus`/`/transition/` action exactly like Modules A and B, per Module H's mandate that no module invents its own permission logic (README.md decision #4). The earlier CKAN detour (2026-09-15 amendment) and the Next.js/Prisma "Module C v0" thin layer are both superseded and retired — do not build against those.

## Endpoints

All endpoints taken from the PRD's own API surface list (`docs/PRDs/C-data-repository-dashboard-integration.md:42-50`), which remains canonical per the 2026-09-19 amendment.

| Method & Path | Auth | Filters | Status |
|---|---|---|---|
| `GET /api/v1/datasets/?sub_theme=&theme=&geography=&year=&q=` | Public read, visibility-filtered | `sub_theme` (exact), `theme` (top-level, via `sub_theme__parent_id`), `geography`, `year`, `q` | **Built** — `apps/datarepo/views.py`'s `DatasetFilter` |
| `GET /api/v1/datasets/{slug}/` | Public read, visibility-filtered | — | **Built, flagged deviation** — see below |
| `GET /api/v1/datasets/{slug}/preview/table/?page=` | Public read, visibility-filtered | `page` | **Built** — `csv`; `parquet` (via `pyarrow`, 50 rows per page, non-JSON cell types stringified); `zip` (first `.csv` member). An unreadable file, or a zip with no CSV, returns `422` |
| `GET /api/v1/datasets/{slug}/preview/map/` | Public read, visibility-filtered | — | **Built** — `geojson` datasets only: the file is parsed and returned as-is for the frontend to render (10 MB cap, `413` above it). A non-`geojson` dataset, or a file that isn't valid GeoJSON, returns `422` |
| `GET /api/v1/datasets/{slug}/download/` | Public for the `public` tier; signed-in with an approved request for `on_request` | — | **Built** |
| `POST /api/v1/datasets/{slug}/request-access/` | Authenticated | — | **Built** — creates an `AccessRequest` |
| `POST /api/v1/datasets/{slug}/transition/` | Auth (role-gated) | — | **Built** — shared `WorkflowViewSetMixin` action, same as A/B |
| `GET /api/v1/dashboards/?theme=&geography=&year=&type=` | Public read, published only | `theme`, `geography`, `year`, `type` | **Built** — `theme` here is a direct FK (Dashboard wasn't asked to require a sub-theme, unlike Dataset) |
| `GET /api/v1/access-requests/?status=&dataset=` | Editor/Admin only | `status`, `dataset` | **Built, addition beyond this doc** — needed so staff can discover which `{id}`s are pending before the `PATCH` below is usable |
| `PATCH /api/v1/access-requests/{id}/` | Editor/Admin only | — | **Built** — proposed shape below, now implemented |

### Flagged deviation — dataset lookup by `{slug}` not `{id}`

PRD line 44 literally writes `GET /api/datasets/{id}/`. Every other in-scope module (Module A's content types, Module B's `Publication`) uses slug-based lookups, and `datarepo_dataset` itself has a unique `slug` column (ERD `docs/erd/pri_platform_schema.sql:434`). Recommending `{slug}` for API consistency across the whole contract — flagged here for explicit confirmation rather than silently deviating from the PRD's literal text.

### Proposed — `AccessRequest` approve/deny queue

PRD line 50 explicitly defers this: *"Admin-facing endpoints (approve/deny access requests, upload/tag/set-visibility, workflow transitions) exist but their exact shapes are a build-time detail, not fixed here."* Proposing, not committing:

```
PATCH /api/v1/access-requests/{id}/
Body: {"status": "approved" | "denied"}
```
Mirrors the existing `/transition/` pattern (single-field status update, role-gated, writes `AuditLog`) rather than inventing a new shape. Editor/Admin only, matching PRD story 9.

## Data model (built)

Per PRD Implementation Decisions (`docs/PRDs/C-data-repository-dashboard-integration.md:31-41`), matching ERD tables (`docs/erd/pri_platform_schema.sql:432-496`) and `apps/datarepo/models.py`:

- **`Dataset`** — `slug`, `title`, `description`, `file` (S3 key, see [README.md](README.md#file-storage)), `format` (`csv`/`parquet`/`zip`), `sub_theme` (FK to `taxonomy.Theme`, renamed from the originally-planned `theme` — **must reference an actual sub-theme**, enforced in `DatasetSerializer.validate_sub_theme`; see [README.md](README.md#shared-taxonomy--theme)), `geography`, `year`, `source`, `update_frequency`, `visibility` (`public`/`on_request`/`internal_only`), plus `WorkflowMixin`'s `status`/`created_by`/`reviewed_by`/timestamps.
- **`Dashboard`** — `slug`, `title`, `description`, `embed_url`, `embed_type` (`datawrapper`/`tableau`/`d3`), `theme` FK (direct, to any `Theme` — **not** rescoped to sub-themes-only, unlike `Dataset`/`Publication`), `geography`, `year`, `type`, linked `Dataset`(s) (M2M), plus `WorkflowMixin` fields.
- **`AccessRequest`** — `user` FK, `dataset` FK, `status` (`pending`/`approved`/`denied`), `requested_at`, `reviewed_at`, `reviewed_by`. Unique per (`user`, `dataset`).

## Descriptive fields and file stats

- `granularity` (e.g. "District, Year"), `time_period` (e.g. "2014-15 to 2024-25") and `citation` (custom citation text; clients build a default one when it's blank): optional and editable.
- `row_count`, `column_count` and `columns` (the column names): read-only, worked out from the file whenever it changes (`Dataset.save()`): data rows for CSV, the first CSV in a ZIP and Parquet; features and property names for GeoJSON. A file that can't be read leaves them empty (`null`, `null`, `[]`) and never fails the save. Migration `datarepo.0005` fills them for existing datasets; `manage.py refresh_dataset_stats` recomputes them all.
- `Theme.description`: optional overview for a theme's page.

## Collections

`GET/POST /api/v1/collections/`, `/collections/{slug}/` (workflowed, as datasets): a named bundle of related datasets, for example everything behind one data story. `datasets` is a list of dataset slugs and `publication` an optional publication slug, both written by slug. Each caller sees only the datasets it could open itself: the same workflow and visibility-tier rules as the dataset endpoints, so a collection never reveals a draft or internal dataset, not even its slug.

## Visibility enforcement (server-side, not UI hiding)

Carried verbatim from PRD lines 36-39 — this is the module's core correctness guarantee:

- **`public`** — appears in search, preview and download open to anyone, including anonymous visitors, once the dataset is published (see [README.md](README.md#default-permission-model)).
- **`on_request`** — appears in search with metadata and a "request access" action; preview may show a reduced/sample level (decide at build time); full download blocked until that user's `AccessRequest` is `approved`.
- **`internal_only`** — **PRD's own flagged-for-stakeholder-confirmation assumption**, carried through unchanged: fully excluded from search/listing/detail for any non-staff (non Editor/Researcher/Admin) request — not just download-gated, genuinely invisible. Confirm with PRI before implementing, per the PRD's explicit note (line 118). **Implementation note:** since PRD line 39 frames `internal_only` as existing "for Admin/Editor/Researcher-authenticated internal use," download is gated to that same three-role group, not narrowed to Editor/Admin only — a Researcher who can see an `internal_only` dataset can also download it.

## Preview endpoints — server-computed, not raw downloads

Table preview returns paginated rows, not the whole file; map preview returns simplified/pre-processed geo data — protects large-file performance and, for `on_request` datasets, the underlying full file (PRD line 40).

## Explicitly excluded from v1

Per `docs/erd/README.md:100-108, 121-123`, and because PRD C's own endpoint list doesn't enumerate any of these:

- **`AccessGroup` / membership / grant endpoints** (`datarepo_accessgroup`, `_member`, `_grant`) — ERD-modeled (bulk cohort access, e.g. "Kerala MLAs 2026"), implied by the PRD's data-model bullet but not named in its API surface list. Likely needed eventually, not drafted here.
- **`datarepo_downloadlog`, `datarepo_favorite`** — ERD README labels both "recommended additions, no PRD names them" (confirmed only in the live prototype's mock account dashboard).

## Testing priority (carried from PRD, line 54)

*"The visibility-tier and access-request logic is a data-leak risk if wrong ... Prioritize external-behavior tests at the API boundary for exactly those three tiers × the relevant roles, before testing anything else in this module."* This is this module's single highest-priority test once built — an `internal_only` or un-approved `on_request` dataset must never be reachable via any endpoint by an unauthorized role.

## Out of scope (per PRD, line 56-62)

- Building the third-party visualization tools (Datawrapper/Tableau/D3) — stores references/embeds only.
- Full user account system beyond holding/checking access grants.
- Dataset licensing/DOI generation — future phase.
- Publication Repository (Module B) — separate module.
- ElasticSearch — Postgres filter/search assumed sufficient for v1.
