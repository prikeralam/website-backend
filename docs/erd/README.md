# PRI Platform ER Diagram

`pri_platform_schema.sql` is a Postgres-flavored DDL script covering the **entire PRI
platform** — all 8 backend modules (A–H) plus the existing Projects app and the shared
accounts/workflow core — as a single ER diagram source file. It is a design artifact, not
a Django migration: nothing here runs against a live database.

## Exploring locally with sample data (SQLite)

`pri_platform_sample.db` is a ready-to-open SQLite database with the same 55 tables, seeded
with ~315 rows of realistic, hand-linked sample data — open it in any local SQLite GUI (DB
Browser for SQLite, TablePlus, DataGrip, DBeaver) to click through the actual foreign-key
relationships instead of just reading them off the diagram.

**Content is grounded in the real PRI prototype** — both `front end/app/_content/*.ts` and the
live site (https://pri-website-pink.vercel.app/) — wherever that content exists: the actual team
roster, executive council, patrons, partner institutions, the "Kerala in Data" publication
series, the real 5 research-wing departments and their sub-areas, the real office address and
legal registration numbers, and real event/job-listing titles — clearly extended with invented
rows (donors, extra applications, media-watch cases, etc.) where the prototype has no real data
yet, since several modules (D–H) aren't built or seeded on the live site either.

**Every enum-constrained column has at least one row for every one of its allowed values** —
e.g. all 5 workflow statuses, all 8 `PersonProfile` groups, all 7 publication formats, all 3
dataset visibility tiers, all 6 fellowship application statuses, all 4 media-case statuses, all
5 `content_event.event_type` values, all 2 `content_partner.partner_type` values, all 3
(post-fix) `datarepo_dataset.format` values. This is checked automatically: `build_sample_db.py`
parses every `CHECK (col IN (...))` constraint out of its own schema and fails the build if any
allowed value has zero rows.

Regenerate it any time with:

```bash
python docs/erd/build_sample_db.py
```

If `pri_platform_sample.db` is open in a SQLite GUI at the time (locked for writing), the script
builds into `pri_platform_sample.rebuild.db` instead and tells you to close the GUI and rename it
into place — it never silently fails or corrupts the open file.

This is a design/exploration aid only — schema and data live in `build_sample_db.py`, translated
to SQLite syntax (no JSONB/array types; JSON and tags are stored as TEXT holding a JSON string).
It is not a Django migration and isn't wired to `apps/*/models.py`.

## Importing into Lucidchart

1. In Lucidchart: **File → Import Data → Import from SQL** (or **New Document → Import from SQL**, depending on your Lucidchart plan/version).
2. Upload `pri_platform_schema.sql`.
3. Lucidchart parses the `CREATE TABLE` statements and generates a full ER diagram, including foreign-key relationship lines, cardinality, and column types/constraints.
4. Arrange into swimlanes by module if useful — the file is grouped and commented by module (Core/H, Shared Taxonomy & Site Config, A, Projects, B, C, D, E, F, G) in that order, matching the section headers in the SQL.

## Source grounding

- **Core, Module A (all 4 content types), Projects, and Module B (`Publication` base fields)** reflect what is actually implemented in `apps/*/models.py` as of 2026-09-17 — these are ground truth, not just spec.
- **Module B's versioning/tagging/DOI fields, and all of Modules C–H**, are modeled from the PRDs in the frontend repo (`front end/docs/PRDs/backend/A-H.md`) and **do not exist as code yet**. Treat those tables as the target design, provisional until each module is actually built — expect small adjustments once real implementation starts.

## Module C — native Django, not CKAN

The Module C PRD (`C-data-repository-dashboard-integration.md`) has a 2026-09-15 amendment
stating Module C would be built on CKAN, with a thin Next.js/Prisma layer (`app/api/datasets/*`
in the frontend repo) owning the `public`/`on_request`/`internal_only` visibility model and
`AccessRequest` workflow.

**That decision has been superseded (2026-09-17): the data repository is now being built
natively in this Django backend instead of CKAN.** `datarepo_dataset`, `datarepo_dashboard`,
`datarepo_dashboard_datasets`, and `datarepo_accessrequest` in this schema are modeled from
the PRD's original (pre-CKAN) *Implementation Decisions* section — the same visibility tiers,
access-request flow, and preview-endpoint shape, just as first-class Django models/tables
instead of split across CKAN + a Prisma thin layer. The frontend repo's PRD amendment is now
out of date and should be revisited/updated to match.

## Fields added beyond current code

A few columns were added to already-built models because downstream PRDs need them and they
don't exist in `apps/*/models.py` yet — flagged inline in the SQL with a comment:

- `content_document.document_type`, `content_document.year` — needed for Module A/F's annual-report and document-type filtering.
- `publications_publication.external_id`, `.visibility`, `.tags` — needed for Module B's DOI/slug, public/private toggle, and tag-based filtering (the current model only has a single `theme` field).
- `datarepo_dataset.tags`, `.coverage`, `.last_updated`, `.file_size`, `.download_count`, `.type` — needed to match the metadata actually shown on the live site's dataset detail page (Metadata tab), plus its `format` CHECK constraint fixed from `csv/xlsx/geojson/spss` to `csv/parquet/zip` to match what the live site actually offers.
- `datarepo_dashboard.theme_id`, `mediawatch_mediacase.theme_id` — needed once Theme became a shared taxonomy (see below); `mediawatch_mediacase` previously had no theme field at all, despite its own PRD's public API filtering by `?theme=`.
- `fellowship_application.intake_channel` — nullable, hedges an explicitly unresolved PRD question (see below).

These are design recommendations for when those modules/fields are actually built, not a
statement that they exist in the current migrations.

## Theme as a shared taxonomy

Modules A, B, C, and E each independently describe "theme" as a controlled vocabulary meant to
be shared across the platform's filter UIs, not free text per table — confirmed directly on the
live site (the Research Hub, Data Repository, and dataset/publication submission forms all draw
from the same 8-value list: Education, Employment, Economics, Public Finance, Health, Governance,
Demography, Migration). `taxonomy_theme` is the shared lookup table; `publications_publication`,
`datarepo_dataset`, and `datarepo_dashboard` now FK to it via `theme_id` instead of storing a free-text
`theme` string, and `mediawatch_mediacase` gets a new nullable `theme_id` (not every flagged case
maps cleanly onto a research theme). `projects_project` was deliberately left theme-free — no PRD
evidence it needs one. `content_department`/`content_departmentarea` (the About page's 5 research
wings) is a separate, unrelated lookup — the departments don't map 1:1 onto the 8 themes (e.g.
"Department of Society Development" has no matching theme).

## Group-based dataset access

Alongside the existing per-user `datarepo_accessrequest` (one row per user per dataset), 
`datarepo_accessgroup` + `datarepo_accessgroup_member` + `datarepo_accessgroup_grant` let staff
grant a whole named cohort — e.g. "Kerala MLAs 2026" — access to a set of `on_request` datasets in
one action, instead of bulk-approving individual requests. Effective access to an `on_request`
dataset is: an approved individual `AccessRequest` **OR** membership in a group holding an active
(non-expired) grant on that dataset. `internal_only` datasets stay staff-only regardless of group
membership.

## PRD-confirmed vs. recommended additions

Most of the tables added in this update are directly named or strongly implied by the backend
PRDs (`taxonomy_theme`, the access-group trio, the publication-body tables, `content_event`,
`content_joblisting`, `content_partner`, `content_namedprogram`, `content_album`/`galleryphoto`,
`content_office`, `content_department`/`departmentarea`, `fellowship_programtimelinestage`,
`mediawatch_response_attachment`, `donors_webhookevent`). A smaller set are **recommended
additions with no PRD naming them explicitly**, motivated either by real functionality already
built in the live prototype's mock frontend, or by a cross-module gap independently implied by
multiple PRDs:

- `accounts_apikey` — confirmed built in the live prototype's account dashboard (mock API key with regenerate), but no PRD anywhere mentions API-key/programmatic access.
- `datarepo_downloadlog`, `datarepo_favorite` — confirmed built in the live prototype's account dashboard (download history, starred datasets), not named in any PRD.
- `accounts_notificationlog` — Modules D, F, and G each independently require reliable auto-email-on-status-change, but no PRD names a backing table for it.

## Sensitive fields

`core_sitesettings.bank_account_name`/`.bank_account_number`/`.bank_ifsc`/`.bank_name_branch` are
sensitive (the org's bank transfer details, shown on the live `/donate` page) — a real Django
implementation needs field-level access control (e.g. admin-only serializer fields), not just
object-level row permissions.
