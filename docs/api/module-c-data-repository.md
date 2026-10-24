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
| `GET /api/v1/datasets/{slug}/download/?format=` | Public for the `public` tier; signed-in with an approved request for `on_request` | `format` | **Built** — the main file, or the file in `format` (see "Several formats" below); `404` when the dataset has no file in that format |
| `POST /api/v1/datasets/{slug}/files/` | Who may edit the dataset: its contributor creator while it's a draft, editors and admins always | — | **Built** — multipart `format`, `file`: adds the same data in another format |
| `DELETE /api/v1/datasets/{slug}/files/{id}/` | As above | — | **Built** — removes one extra format and deletes its stored file |
| `POST /api/v1/datasets/{slug}/request-access/` | Authenticated | — | **Built** — creates an `AccessRequest` |
| `GET /api/v1/datasets/{slug}/releases/` | Public read, visibility-filtered | — | **Built** (#125) — version history: published releases, newest first; staff and each release's creator also see the others. `files` only for callers `/download/` allows |
| `POST /api/v1/datasets/{slug}/releases/` | Editors, admins and the dataset's contributor creator | — | **Built** (#125) — multipart `version`, `changelog`, `format`, `metadata` (JSON), `files[<format>]`; see "Releases" below |
| `GET`/`PATCH`/`DELETE /api/v1/datasets/{slug}/releases/{id}/` | Read as above; `PATCH` editors and admins (`qa_checklist`); `DELETE` the creator of a draft, or staff before publication | — | **Built** (#125) |
| `POST /api/v1/datasets/{slug}/releases/{id}/files/` | The release's creator or staff, while it is a draft | — | **Built** (#125) — multipart `format`, `file` |
| `POST /api/v1/datasets/{slug}/releases/{id}/transition/` | The creator for `draft -> in_review`, otherwise editors and admins | — | **Built** (#125) — `{"status": ...}` with the dataset's gate and two-person rule |
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

- **`Dataset`** — `slug`, `title`, `description`, `file` (S3 key, see [README.md](README.md#file-storage)), `format` (`csv`/`parquet`/`zip`/`geojson`/`json`/`xlsx`), `file_size` (bytes, read-only), `sub_theme` (FK to `taxonomy.Theme`, renamed from the originally-planned `theme` — **must reference an actual sub-theme**, enforced in `DatasetSerializer.validate_sub_theme`; see [README.md](README.md#shared-taxonomy--theme)), `geography`, `year`, `source`, `update_frequency`, `visibility` (`public`/`on_request`/`internal_only`), plus `WorkflowMixin`'s `status`/`created_by`/`reviewed_by`/timestamps.
- **`Dashboard`** — `slug`, `title`, `description`, `embed_url`, `embed_type` (`datawrapper`/`tableau`/`d3`), `theme` FK (direct, to any `Theme` — **not** rescoped to sub-themes-only, unlike `Dataset`/`Publication`), `geography`, `year`, `type`, linked `Dataset`(s) (M2M), plus `WorkflowMixin` fields.
- **`AccessRequest`** — `user` FK, `dataset` FK, `status` (`pending`/`approved`/`denied`), `requested_at`, `reviewed_at`, `reviewed_by`. Unique per (`user`, `dataset`).

## Descriptive fields and file stats

- `granularity` (e.g. "District, Year"), `time_period` (e.g. "2014-15 to 2024-25") and `citation` (custom citation text; clients build a default one when it's blank): optional and editable.
- `row_count`, `column_count` and `columns` (the column names): read-only, worked out from the file whenever it changes (`Dataset.save()`): data rows for CSV, the first CSV in a ZIP and Parquet; features and property names for GeoJSON. A file that can't be read leaves them empty (`null`, `null`, `[]`) and never fails the save. Migration `datarepo.0005` fills them for existing datasets; `manage.py refresh_dataset_stats` recomputes them all.
- `Theme.description`: optional overview for a theme's page.

## Several formats of one dataset

A dataset's main file (`file`, `format`) is the one previews, row counts and columns come from. The same data can also
be uploaded in other formats (`DatasetFile`: one file per format, never the main format), so a dataset is one record
with one description, citation and access level, whatever formats it comes in.

- `files` (read-only) lists every downloadable file, the main one first: `[{id, format, label, url, size}]` (`id` is
  `null` for the main file, which is replaced through the dataset itself). Like `file`, it is left out entirely for
  callers who may not download the dataset, so an `on_request` or `internal_only` dataset's formats never leak.
- `formats` (read-only) lists the format codes, main first, and is always shown, so visitors can see what an
  `on_request` dataset comes in before asking for it.
- Formats: `csv`, `parquet`, `zip`, `geojson`, `json`, `xlsx`. Previews read only `csv`, `parquet`, `zip` (table) and
  `geojson` (map), so a dataset whose main file is `json` or `xlsx` has no table preview.
- Adding or removing a format writes an audit-log row (`dataset_file_added` / `dataset_file_removed`). Deleting a
  dataset deletes its extra files from storage too.
- The system doesn't check that the formats hold the same data; the counts shown are the main file's.

## Publishing framework (#123)

Datasets follow the PRI Data Framework (pri-data `docs/FRAMEWORK.md`, build spec `docs/PUBLISHING_PLAN.md` B1-B3).
Their data and metadata come from pri-data's catalog through `pri publish`, which logs in as the `pri-pipeline`
account (role `researcher`) and can only create, edit its own drafts and move them to `in_review`.

**Fields** (migration `datarepo.0009`; all optional in the database, so older datasets stay valid; existing datasets
get an empty `license`, new ones default to `CC-BY-4.0`):

- Identity and text: `code` (permanent ID `PRI-XXX-NNNN`, unique; blank is stored as `null`), `version` (semver),
  `summary` (one sentence), `keywords` (at most 12, trimmed), `methodology`, `known_limitations`.
- Source: `source_publisher` (front ends prefer it over the older `source`), `source_document`, `source_url` (https
  only), `archived_url`, `retrieval_date`, `source_tier` (`1`, `2`, `3`, `4`, `P`), `collection_method`
  (`administrative`, `census`, `sample_survey`, `rti`, `pri_primary`, `compiled`), `source_terms`.
- Coverage: `period_type` (`calendar_year`, `fiscal_year`, `academic_year`, `survey_year`, `snapshot`, `other`),
  `next_update`, `lgd_levels` (levels that carry LGD codes, e.g. `district`).
- `quality_grade` (`A`/`B`/`C`, proposed by `pri publish`, confirmed by QA), `license` (`CC-BY-4.0`,
  `CC-BY-NC-4.0`, `GODL-India`, `ODbL-1.0`, `other`), `steward`, `contact` (e-mail), `related_publications`
  (publication slugs).
- `column_dictionary`: `[{name, label, description, data_type, unit, allowed_values, null_meaning, source_column,
  derived_formula}]`; `name` and `label` required, names unique and, once the file is profiled, real columns.
- `provenance` (pipeline repo, git SHA, run ids, file hashes) and `qa_report` (`pri publish --check` output:
  `{passed, grade_proposed, checks}`), written by the pipeline.
- `qa_checklist`: `{item key: true/false}` for the manual QA checklist; written by editors and admins only.
  `qa_checklist_items` (read-only) lists the keys with their labels, in order, for the review screen.
- `approved_by`, `approved_at` (read-only): set on the move to `approved`, cleared on a move back to `draft` or
  `in_review`.
- Filters: `code`, `source_tier`, `quality_grade`. `?q=` also searches `summary` and `keywords`.

**Publish gate** (`DatasetViewSet.publish_blocker`): `approved -> published` answers 400 with one sentence naming
everything missing when the dataset is not `approved`; any of `code, version, title, summary, description, sub_theme,
source_publisher, source_url, archived_url, retrieval_date, source_tier, collection_method, geography, granularity,
time_period, period_type, update_frequency, methodology, known_limitations, license, steward, quality_grade` is
empty; `source_tier` is `4`; a profiled column has no labelled `column_dictionary` entry; `qa_report.passed` is not
`true`; or any `qa_checklist` item is not done. Datasets published before the gate stay published; an edit that
empties a required field of a published dataset is refused (fields that were never filled can stay empty).

**Two-person rule** (`transition_blocker`, shared by every workflow type through `WorkflowViewSetMixin`): the
creator of a dataset can't approve it ("You created this dataset, so another editor has to approve it."). The
second half, the approver can't publish, is lifted for now (#131) so a single editor can approve and publish; it
will come back once there is a second editor. So a pipeline dataset is submitted by `pri-pipeline` and approved
and published by an editor, each an audit-log row. `after_transition` is the
matching hook for side effects; publications keep their cover rule through `publish_blocker`.

## Releases (#125)

A published dataset is refreshed by a **release** (pri-data `docs/PUBLISHING_PLAN.md` B4), never by unpublishing it:
the new version is uploaded and reviewed beside the live one, and publishing it swaps the files and metadata in one
transaction while the dataset stays published at the same slug. Every published release stays in the version history
with its files, so a cited version remains downloadable.

**Models** (migration `datarepo.0010`): `DatasetRelease` (`dataset`, `version`, `changelog`, `metadata`, `format` of
the main file, `status` `draft`/`in_review`/`approved`/`published`/`rejected`, `qa_checklist`, the main file's
`row_count`/`column_count`/`columns`, `created_by`, `approved_by`/`approved_at`, `published_at`) and
`DatasetReleaseFile` (`release`, `format`, `file`, `size`, `sha256`; one per format). A version is unique per dataset
unless rejected (a rejected release gives its number back), and a dataset has at most one release in `draft`,
`in_review` or `approved` at a time.

**Posting** (`POST /datasets/{slug}/releases/`, multipart): `version` (semver, higher than the dataset's and every
non-rejected release's), `changelog`, `format` (main file), `metadata` (JSON object) and the files as
`files[<format>]`, the main format's required. Further formats can be added to a draft one request each
(`POST .../releases/{id}/files/`), which keeps every upload under the 50 MB nginx limit. Only published datasets take
releases (`400` otherwise); the dataset's contributor creator (`pri-pipeline`) and editors/admins may post.

- `metadata` may set these dataset fields, validated with the dataset's own rules: `title, description, sub_theme,
  geography, year, source, update_frequency, granularity, time_period, citation, code, summary, keywords,
  source_publisher, source_document, source_url, archived_url, retrieval_date, source_tier, collection_method,
  source_terms, period_type, next_update, methodology, known_limitations, lgd_levels, quality_grade, license, steward,
  contact, related_publications, column_dictionary, provenance, qa_report`. Not `slug` (links and citations use it) nor
  `visibility` (an access decision for staff), nor workflow fields.
- `column_dictionary` names must be columns of the release's main file, which is profiled on upload.
- **Baseline.** The first release of a dataset also records the live version as a published release (version = the
  dataset's, `1.0.0` when it has none; changelog "Version published before releases existed."), pointing at the
  dataset's current files, so they stay downloadable after the swap.

**Review** (`POST .../releases/{id}/transition/`): `draft -> in_review` by its creator or staff; `in_review ->
approved | draft | rejected` and `approved -> published | draft | rejected` by editors and admins. The creator can't
approve its own release; the approver may publish for now (#131, as for datasets). Editors tick the release's own
`qa_checklist` with `PATCH .../releases/{id}/`. Every transition, creation, added file and deletion is audit-logged
(`release_*` actions, target `datasetrelease:<id>`).

**Publish gate** (`releases.release_publish_blocker`): the dataset gate, applied to the dataset as it would be after
publishing (the release's metadata over the dataset's fields, the release's version and columns): the release is
`approved` and its dataset `published`, every required field is filled, tier is not 4, every column of the new file
is labelled, the release's `metadata.qa_report.passed` is `true`, its checklist is complete and its main file exists.

**Publish effect** (`releases.publish`, one transaction): the metadata is applied through the dataset serializer, the
dataset's `file`/`format` point at the release's main file and its extra formats are replaced by the release's other
files, `version` becomes the release's, row count, columns and size are worked out again, and the release becomes
`published`. Files are shared, not copied: a stored file is deleted only when no dataset, extra format or release
still points at it (`models.stored_file_in_use`), so deleting a draft release removes its own files and nothing else.
Published releases can't be deleted.

**Deleting** a release: its creator while it is a draft, editors and admins until it is published. The pipeline
replaces a draft that QA returned by deleting it and posting again.

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
