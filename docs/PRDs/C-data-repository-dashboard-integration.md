# Spec: Backend Module C — Data Repository & Dashboard Integration

**Backend module C** · Status: Drafted · Feeds: [Data Repository & Library](../frontend/04-data-repository-library.md) · Depends on: user accounts (introduced by this module for restricted-dataset access; not a separate module in Phase 1)

## Problem Statement

PRI's structured datasets (CSV, XLSX, GeoJSON, SPSS) and the dashboards built from them currently have no backend home: nowhere to upload and version them, no way to tag them with searchable metadata, no enforced distinction between public/on-request/internal-only data, and no API for the frontend to search, filter, and preview them. Without this, the Data Repository & Library page has nothing to consume, and sensitive datasets have no access-control mechanism short of not publishing them at all.

## Solution

A Django backend module that stores and hosts structured datasets and dashboard references, tags them with searchable/filterable metadata (theme, geography, year, type), enforces a three-tier visibility model (public / on-request / internal-only) with a request-approval flow for gated data, and exposes table-preview and map-preview data through a REST API that the frontend's search/filter/detail views consume directly.

## User Stories

1. As a Researcher, I want to upload a dataset file (CSV, XLSX, GeoJSON, or SPSS), so that it becomes available in the data repository.
2. As a Researcher, I want to tag an uploaded dataset with metadata (theme, geography, year, type, source, update frequency), so that it's discoverable through search/filters and its provenance is clear.
3. As a Researcher, I want to set a dataset's visibility tier (public, on request, internal-only) at upload time, so that sensitive data isn't exposed by default.
4. As an Editor/Admin, I want to review and approve a dataset before it's publicly visible, reusing the same Draft→Review→Approve→Publish workflow as other content (Module A), so that data publishing has the same editorial control as other content types.
5. As a visitor, I want to query datasets by theme/geography/year/type via an API, so that the frontend search/filter UI has something to call.
6. As a visitor, I want to fetch a paginated table preview of a dataset without downloading the full file, so that I can evaluate it before committing to a download.
7. As a visitor, I want to fetch map-ready geo data (e.g. GeoJSON) for datasets that have a spatial component, so that the frontend can render an interactive map preview.
8. As a registered visitor, I want to request access to an "on request" dataset, so that I can be considered for approval without needing to email someone manually.
9. As an Admin/Editor, I want a queue of pending access requests I can approve or deny, so that gated datasets aren't distributed without oversight.
10. As a registered visitor whose request was approved, I want to download the dataset file, so that I can use it in my own work.
11. As an Admin, I want internal-only datasets to be unreachable by any Donor/Visitor-role request (no preview, no download, no metadata beyond what's needed to know it exists or not — per the open visibility question flagged in the frontend spec), so that internal data never leaks through the public API by accident.
12. As a Comms/Admin staff member, I want to register a "dashboard" entry (an embed reference/URL to a Datawrapper/Tableau Public/D3.js visualization) linked to one or more datasets, so that the frontend can list and display dashboards alongside raw datasets.
13. As a developer building the Data Repository frontend page, I want a stable, documented API contract for dataset search, dataset detail + metadata, table preview, map preview, dashboard listing, and access-request submission/status, so the frontend can be built against an agreed interface.

## Implementation Decisions

- **Data model (initial set):**
  - `Dataset` — title, description, file (CSV/XLSX/GeoJSON/SPSS), format, theme, geography, year, source, update_frequency, visibility (`public`/`on_request`/`internal_only`), status (shares Module A's Draft→Review→Approve→Publish state machine — this module reuses that shared workflow mixin rather than inventing a second one).
  - `Dashboard` — title, description, embed_url/reference (Datawrapper/Tableau/D3), linked `Dataset`(s), theme/geography/year/type tags (mirrors Dataset's filter fields so both share one search/filter UI on the frontend).
  - `AccessRequest` — requesting user, target `Dataset`, status (`pending`/`approved`/`denied`), timestamps, reviewer — the request-approval queue for `on_request` datasets.
  - A lightweight `UserAccount` concept is introduced here (visitor accounts for requesting restricted-dataset access) — scoped narrowly to "can authenticate and hold access grants," not a full user-profile system; broader account features (if any) belong to future modules/phases.
- **Visibility enforcement (server-side, not just UI hiding):**
  - `public`: dataset appears in search, preview and download open to anyone.
  - `on_request`: dataset appears in search with metadata and a "request access" action; table/map preview may be shown at a reduced/sample level (decide at build time) but full download is blocked until an `AccessRequest` for that user+dataset is `approved`.
  - `internal_only`: **resolves the open question from the frontend spec** — datasets in this tier are excluded entirely from public search/listing/detail responses for any non-staff role; they exist only for Admin/Editor/Researcher-authenticated internal use. This is the stricter "fully hidden" interpretation, chosen because the source doc's phrase "internal-only" reads as excluding the public, not merely gating downloads — flag for stakeholder confirmation, but this is the default unless told otherwise.
- **Preview endpoints are server-computed, not raw file downloads:** table preview returns paginated rows (not the whole file) and map preview returns simplified/pre-processed geo data — protects both large-file performance and, for `on_request` datasets, the underlying full file itself.
- **File storage:** dataset files stored in S3/DigitalOcean Spaces (per project CLAUDE.md), not the database — the `Dataset` model stores a reference/key, not the file contents.
- **API surface (DRF, pending open framework decision — flagged as the module most likely to want an async/FastAPI treatment given "heavy real-time/data" framing in the source doc, but not decided here):**
  - `GET /api/datasets/?theme=&geography=&year=&type=&q=` — search/filter, respects visibility per requester's role/auth state.
  - `GET /api/datasets/{id}/` — detail + metadata (source, coverage, update frequency, visibility state relative to the requester).
  - `GET /api/datasets/{id}/preview/table/?page=` — paginated tabular preview.
  - `GET /api/datasets/{id}/preview/map/` — geo preview data.
  - `GET /api/datasets/{id}/download/` — full file; enforces visibility/access-grant server-side.
  - `POST /api/datasets/{id}/request-access/` — creates an `AccessRequest` for the authenticated user.
  - `GET /api/dashboards/?theme=&geography=&year=&type=` — dashboard listing, same filter shape as datasets.
  - Admin-facing endpoints (approve/deny access requests, upload/tag/set-visibility, workflow transitions) exist but their exact shapes are a build-time detail, not fixed here.

## Testing Decisions

Deferred in detail (no code yet), but flagged as the highest-stakes module to get testing right on: the visibility-tier and access-request logic is a data-leak risk if wrong (an `internal_only` or un-approved `on_request` dataset must never be reachable via any endpoint by an unauthorized role). Prioritize external-behavior tests at the API boundary for exactly those three tiers × the relevant roles, before testing anything else in this module (search/filter correctness, preview pagination, etc.). Reuse whatever test pattern Module A establishes first, since this module builds on Module A's shared workflow mixin.

## Out of Scope

- Building the third-party visualization tools (Datawrapper/Tableau Public/D3.js) — this module stores references/embeds, not chart-rendering logic.
- Full user account system (profile management, password reset flows, etc. beyond what's needed to hold and check access grants) — narrowly scoped per Implementation Decisions above; broader account features are a future-phase concern.
- Dataset licensing/DOI generation (Zenodo/CrossRef, per the source doc's long-term scalability plan) — explicitly future phase.
- Publication Repository Module (B) — separate module for research papers/publications, not datasets.
- ElasticSearch integration — Postgres full-text/filter search is assumed sufficient for Phase 1 per the project's tech stack notes; revisit only if search performance/relevance becomes a real problem.

## Amendment — 2026-09-15

**This module is now being built on CKAN, not the bespoke Django app described above.** Decided with the
user alongside the v1/v3 → v2 site consolidation. What changes and what doesn't:

- **CKAN owns**: dataset/resource storage, search (`package_search`), table/map preview data, theme/
  geography/year/type metadata (via CKAN extras/groups/tags). This runs as its own service in a new
  `pri-ckan` repo (Docker Compose: CKAN + Postgres + Solr + Redis) — not part of this or any Django
  codebase.
- **A thin custom API layer owns**: the `public`/`on_request`/`internal_only` three-tier visibility model
  and the `AccessRequest` approve/deny workflow, exactly as designed in the Implementation Decisions above
  — CKAN only has public/private, so this logic can't live in CKAN itself. For this pass it's implemented
  as Next.js Route Handlers inside `pri-website` (`app/api/datasets/*`) backed by Postgres/Prisma — a
  "Module C v0." The `Dataset`/`Dashboard`/`AccessRequest`/`UserAccount` model design above is otherwise
  unchanged; it's just split across CKAN (catalog data) and this thin layer (access state) instead of
  living entirely in one Django app.
- **Still true**: the API surface shape (search/detail/preview/download/request-access), the visibility
  enforcement rules (`internal_only` fully hidden from non-staff, `on_request` gated on an approved
  `AccessRequest`), file storage off the database, and the open `internal_only` stakeholder-confirmation
  flag.
- **Migration path**: when Module A's Django backend repo is actually created, this thin layer's logic and
  Postgres schema are the direct port target for Module C proper — same data model, same rules, moved into
  Django rather than rebuilt.
- **Dashboards** (`Dashboard` records) are not stored in CKAN — CKAN has no native concept matching
  "embedded Datawrapper/Tableau/D3 reference" — they remain hand-authored content in the frontend repo, as
  already scoped under Out of Scope above.

## Amendment — 2026-09-19

**The CKAN pivot above (2026-09-15) is reversed.** Module C moves back to being a bespoke
Django + DRF app — the Implementation Decisions section at the top of this spec (data model,
visibility enforcement, API surface) is canonical again, unamended, and now lives in the
`pri-backend` repo alongside Modules A/B/D–H (rather than in `pri-website`), using the same
`workflow.WorkflowMixin`, permission classes, and role model that Module A/H already established
there — not the standalone Next.js/Prisma "Module C v0" layer described in the 2026-09-15
amendment.

- **`pri-ckan` is decommissioned.** The CKAN + Postgres + Solr + Redis stack is no longer part of
  the plan; that repo is retired, not left running unused.
- **What carries over from the CKAN pass:** the three-tier visibility model
  (`public`/`on_request`/`internal_only`) and the `AccessRequest` approve/deny workflow are
  unchanged in shape — they just move from `prisma/schema.prisma` in this repo into Django models
  in `pri-backend`, matching the original Implementation Decisions above rather than the amended
  CKAN split.
- **Not yet migrated (as of 2026-09-19):** `pri-website`'s `app/api/datasets/*` route handlers,
  `app/_lib/ckan.ts`, and `prisma/schema.prisma` are still the CKAN-era code and still call a CKAN
  instance (`CKAN_URL`, unset in production) — this is a live bug, not just stale docs: the `/data`
  route is currently broken in production because of it. Cutting the frontend over to call
  `pri-backend`'s new datasets API instead is unstarted follow-up work, tracked separately from
  this doc update.

## Further Notes

- Source: docx Backend §2.C "Data Repository & Dashboard Integration" — "Upload/host structured datasets (CSV, XLSX, GeoJSON, SPSS); Visualize through APIs with Datawrapper, Tableau Public, or D3.js; Metadata tagging for filters: theme, geography, year, type; Option to make datasets 'public,' 'on request,' or 'internal-only'; Preview options (table view, map view)."
- **Needs stakeholder confirmation:** the `internal_only` = "fully hidden from public listing" interpretation above is an assumption, not a directive from the source doc — confirm with PRI before building the visibility-filtering logic, since it's cheap to change now and expensive once the frontend and API contract are built against it.
- **Open decision carried from CLAUDE.md:** Django+DRF vs. FastAPI hybrid. This module's dataset/dashboard read endpoints are the strongest candidate in the whole project for a FastAPI hybrid (async, data-heavy, potentially high query volume) if that path is chosen — but nothing in this spec requires it; confirm before scaffolding.
