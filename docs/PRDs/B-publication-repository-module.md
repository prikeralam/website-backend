# Spec: Backend Module B — Publication Repository Module

**Backend module B** · Status: Drafted · Future phase — not yet prioritized for build · Feeds: [Research & Publications Hub](../frontend/03-research-publications-hub.md) · Depends on: [Module A — CMS](A-content-management-system.md) (shared workflow, person profiles)

## Problem Statement

PRI's research reports, working papers, briefs, and explainers need durable, versioned, citable storage with rich metadata (authors, abstract, tags, DOI/slug) that a generic content block can't provide — without it, publications either get crammed into Module A's simpler content types (losing citation/versioning capability) or have nowhere to live at all, and there's no way for external researchers to properly cite PRI's work.

## Solution

A dedicated repository module for uploading and hosting PDFs, data visualizations, and videos as formal publications, with rich bibliographic metadata, file versioning and categorization, a public/private download toggle, and citation export in standard formats (BibTeX, RIS, APA).

## User Stories

1. As a Researcher, I want to upload a publication file (PDF, data visualization, or video), so that it becomes part of the formal repository.
2. As a Researcher, I want to attach metadata (title, authors, abstract, date, tags, DOI/slug) to a publication, so that it's properly cited and discoverable.
3. As an Editor, I want new publications to go through Draft→Review→Approve→Publish before appearing publicly, so that only vetted work is credited to PRI.
4. As a Researcher, I want to upload a revised version of an existing publication, so that corrections/updates are tracked rather than silently overwriting the original.
5. As a visitor, I want to see which version of a publication I'm viewing/downloading, so that I know if it's current.
6. As an Editor, I want to categorize publications by thematic tag, so that the Research & Publications Hub's filtering works correctly.
7. As an Editor, I want to toggle a publication between public and private/restricted download, so that not-yet-public or sensitive work isn't downloadable by anyone.
8. As a visitor, I want to export a citation for a publication in BibTeX, RIS, or APA format, so that I can use it directly in my own reference manager or paper.
9. As a developer building the Research & Publications Hub, I want a stable API for searching/filtering publications and fetching citation exports, so that the frontend can be built against an agreed contract.
10. As an Admin, I want an audit trail of who uploaded, reviewed, approved, and published each publication (reusing Module A's shared workflow audit fields), so that accountability is traceable.
11. As a Researcher, I want to link a publication to my author profile (Module A's `PersonProfile`), so that it appears on my public profile page.

## Implementation Decisions

- **Data model:** `Publication` (title, authors[] → FK to Module A `PersonProfile`, abstract, date, tags[], format: report/working-paper/brief/explainer/infographic/video/data-story, DOI/slug, visibility: public/private, status — reuses Module A's shared workflow mixin), `PublicationVersion` (file, version number, uploaded_by, created_at — a `Publication` has one or more versions; the "current" version is what's served by default, older versions remain retrievable).
- **Versioning:** modeled as a one-to-many `PublicationVersion` per `Publication` rather than overwriting a single file field — matches the doc's explicit "file versioning" requirement and avoids losing prior versions.
- **Citation export:** generated server-side from the `Publication`'s structured metadata (authors, title, date, DOI/slug) into BibTeX/RIS/APA text formats on request — not stored pre-rendered, since metadata edits should immediately reflect in exports.
- **Visibility toggle:** binary public/private per `Publication` (simpler than Module C's three-tier model, matching the doc's explicit "public/private download toggle" language for this module specifically) — private publications are excluded from public list/detail responses, same enforcement discipline as Module C's visibility gating.
- **API surface:** `GET /api/publications/?theme=&format=&q=&author=` (search/filter, public only for unauthenticated), `GET /api/publications/{slug}/` (detail), `GET /api/publications/{slug}/download/?version=` (defaults to current version), `GET /api/publications/{slug}/citation/?format=bibtex|ris|apa` (citation export), admin-only write/versioning/workflow-transition endpoints (exact shape deferred to build time).

## Testing Decisions

Deferred — no code yet. Prioritize testing the visibility toggle (private publications never reachable via public endpoints) and citation-export correctness (each format produces syntactically valid, metadata-accurate output) — both are externally observable, high-consequence behaviors. Reuse Module A's test pattern for the shared workflow state machine rather than re-testing it here.

## Out of Scope

- Full-text search inside publication PDFs — metadata/tag search only, consistent with how the Research & Publications Hub spec scopes search.
- DOI registration/minting (assigning real, external DOIs) — the doc says "DOI/slug" as a metadata field, implying it can be either an internally-generated slug or an externally-issued DOI recorded here, not that this module mints DOIs itself; real DOI issuance (e.g. via Zenodo/CrossRef) is explicitly flagged as a future/long-term item in the source doc.
- Peer-review workflow beyond the standard Draft→Review→Approve→Publish — no separate peer-review process is specified.

## Further Notes

- Source: docx Backend §2.B "Publication Repository Module" — "Upload PDFs, data visualizations, and videos; Metadata fields: title, authors, abstract, date, tags, DOI/slug; File versioning and categorization; Public/private download toggle; Export citation (BibTeX, RIS, APA)."
- Author linking depends on Module A's `PersonProfile` model and its `group` tagging decision (see [Module A](A-content-management-system.md) spec) — this module is the concrete case that motivated making `group` extensible beyond governance.
- DOI/real external identifier issuance is explicitly named in the source doc's long-term scalability plan (via Zenodo/CrossRef) — treat as a future enhancement to this module's `Publication.DOI` field, not a Phase-1-adjacent requirement.
