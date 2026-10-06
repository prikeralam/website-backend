# Module B — Publication Repository

Source PRD: `docs/PRDs/B-publication-repository-module.md`. See [README.md](README.md) for auth, permission matrix, pagination, and file-storage conventions shared across all modules.

Reuses `apps/workflow`'s shared `WorkflowMixin`/`/transition/` action, same as Module A — PRD line 17 explicitly requires the same Draft→Review→Approve→Publish gate.

## Endpoints

| Method & Path | Auth | Filters | Status |
|---|---|---|---|
| `GET /api/v1/publications/?format=&sub_theme=&theme=&language=&status=&q=` | Public read (published, `public` visibility) | `format`, `sub_theme` (exact), `theme` (top-level, via `sub_theme__parent_id`), `language`, `status`, `q` (title/abstract search) | **Built** — `apps/publications/views.py`'s `PublicationFilter` |
| `GET/POST /api/v1/publications/` | Public read; write: contributor | — | **Built** |
| `GET/PATCH/DELETE /api/v1/publications/{slug}/` | Auth (own draft or staff) | — | **Built** — `lookup_field = "slug"` |
| `POST /api/v1/publications/{slug}/transition/` | Auth (role-gated) | — | **Built** — shared action |
| `POST /api/v1/publications/{slug}/versions/` | Contributor role | — | **Built** — creates a `PublicationVersion`, unsets `is_current` on the prior one |
| `GET /api/v1/publications/{slug}/download/?version=` | Public, visibility-gated | `version` (defaults to current) | **Built** |
| `GET /api/v1/publications/{slug}/citation/?format=bibtex\|ris\|apa` | Auth | `format` | **Built** — `apps/publications/citations.py`, generated server-side on request, not stored |

## Data model (built)

Per PRD's Implementation Decisions (`docs/PRDs/B-publication-repository-module.md:27-33`), matching `apps/publications/models.py`:

- **`sub_theme`**: FK to `taxonomy.Theme` (renamed from the originally-planned `theme`) — **must reference an actual sub-theme** (a `Theme` whose own `parent` is set), not a top-level theme; enforced in `PublicationSerializer.validate_sub_theme` (400 if violated), not at the DB level. One sub-theme can be linked from many publications (one-to-many, layered under `Theme`'s own theme→subtheme one-to-many — see [README.md](README.md#shared-taxonomy--theme)). `?theme=<id>` filters by the top-level theme regardless of which of its sub-themes was used.
- **`format`**: 7 choices — `report`/`working_paper`/`brief`/`explainer`/`infographic`/`video`/`data_story`.
- **`external_id`** — DOI if issued else internal slug (PRD line 29). Not a v1 requirement to mint real DOIs (PRD Out of Scope, line 42).
- **`visibility`** — `public`/`private` (PRD line 32). Enforcement: private publications excluded from public list/detail responses — same discipline as Module C's tiers.
- **`tags`** — Postgres `ArrayField`.
- **`cover`** — optional uploaded cover image beside `cover_url`; same rules as Module A's image uploads (JPG/PNG/WebP, 5 MB, `null` removes, the upload wins when both are set).
- **`PublicationVersion`** — `publication` FK, `version_number`, `file`, `uploaded_by`, `is_current`, `created_at` (PRD line 29-30). `file` uses the S3-backed storage decision (see [README.md](README.md#file-storage)).

## Citation export

Generated server-side from `Publication`'s structured metadata (authors, title, date, `external_id`) into BibTeX/RIS/APA text on request — explicitly *not* pre-rendered/stored, so metadata edits immediately reflect in exports (PRD line 31). No new model needed, just a formatting function per target format.

## Flagged, not committed — publication body/data-story tables

`docs/erd/README.md:110-119` lists `publications_publication_block`, `_source`, `_datastory`, `_datastory_stat`, `_datastory_chart` as "PRD-confirmed or strongly implied." However, Module B's actual backend PRD text in this repo (`docs/PRDs/B-publication-repository-module.md`) — read in full for this contract — only specifies `Publication` and `PublicationVersion` in its Implementation Decisions; it does not mention generic body blocks, a bibliography/sources list, or Data Story–specific enrichment fields anywhere. That richer structure most likely originates in the frontend's Research & Publications Hub PRD (referenced by Module B's PRD header as `../frontend/03-research-publications-hub.md`), which is not present in this repo's `docs/` copy.

**Not included as committed v1 endpoints.** Recommend confirming against that frontend PRD (or pulling it into this repo) before treating those ERD tables as build targets.

## Out of scope (per PRD, line 39-43)

- Full-text PDF search — metadata/tag search only.
- Real DOI registration/minting (Zenodo/CrossRef) — future/long-term per the source doc.
- Peer-review workflow beyond the standard Draft→Review→Approve→Publish gate.
