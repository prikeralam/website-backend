# Spec: Backend Module E — Media Watch & Rapid Response Module

**Backend module E** · Status: Drafted · Future phase — not yet prioritized for build · Feeds: [Media Watch & Rapid Response Section](../frontend/07-media-watch-rapid-response.md) · Depends on: none (self-contained, though it shares Module A's file-storage conventions)

## Problem Statement

Tracking misinformation, hate speech, and biased coverage requires internal capture and classification of flagged media items before any public response can be prepared — without a system for this, flagging happens ad hoc (screenshots, informal notes), there's no consistent classification taxonomy, no review step before something is treated as confirmed, and no way to spot trends across many cases.

## Solution

An internal module for uploading and tagging flagged media items (images, headlines, videos), classifying them (hate speech, misinformation, communal bias, etc.), routing them through an internal review/flagging step, surfacing a trends dashboard (by source, keyword, date), and archiving cases with filters — feeding the public Media Watch section once a case has an approved response.

## User Stories

1. As a Researcher, I want to upload a flagged media item (image, headline text, or video) with a note on why it's flagged, so that it enters the review queue.
2. As a Researcher, I want to classify a flagged item (hate speech, misinformation, communal bias, or another type), so that cases are consistently categorized.
3. As an Editor, I want to review a flagged item and confirm or reject the classification, so that only vetted cases proceed toward a public response.
4. As an Editor, I want to attach a response (rebuttal, op-ed, explainer, video, press statement, toolkit assets) to a confirmed case, so that PRI's position is documented against the specific flagged item.
5. As an Editor, I want to mark a case+response as ready for public release, so that it becomes visible on the public Media Watch section only once approved.
6. As an Admin, I want a trends dashboard showing flagged-item volume by source, keyword, and date, so that I can identify patterns worth a coordinated response.
7. As an Admin, I want to search/filter the full case archive (public and internal-only cases) by theme, source, or date, so that I can find any case regardless of its public-release status.
8. As a Researcher, I want to tag a case with source information (which outlet/account), so that trend analysis by source is possible.
9. As an Admin, I want role-gated access so only Researcher/Editor/Admin roles can view or act on flagged items before public release, so that unconfirmed classifications aren't exposed prematurely.
10. As a developer building the public Media Watch page, I want a stable API that only ever returns cases marked public+published, so that internal-only or pending cases can never leak through the public-facing endpoints.
11. As an Admin, I want an audit trail of who flagged, reviewed, and approved each case, so that classification decisions are traceable.

## Implementation Decisions

- **Data model:** `MediaCase` (item reference: image/text/video, classification tag, source, flagged_by, flagged_at, status: flagged/under_review/confirmed/public — the "public" state is the gate the frontend endpoint checks), `Response` (case FK, type: rebuttal/op-ed/explainer, body/file attachments, published_by, published_at).
- **Classification taxonomy:** a controlled tag set (hate speech, misinformation, communal bias, + extensible) rather than freeform text, so trend analysis and filtering stay reliable — mirrors the controlled-vocabulary approach used for thematic tags elsewhere (Module A/B/C).
- **Review gate:** a case only becomes visible to the public API once it reaches `public` status, which requires both a confirmed classification AND a published `Response` — this two-part gate (classification confirmed + response published) prevents a half-finished case from leaking, and is the module's core correctness guarantee.
- **Trends dashboard:** an internal, aggregate query view (counts by source/keyword/date over `MediaCase` records) rather than a separately maintained dataset — computed on read, not pre-materialized, unless volume later requires caching.
- **File handling:** flagged-item media and response assets stored via the same S3/DO Spaces convention used elsewhere (per project CLAUDE.md), not a separate storage mechanism.
- **API surface:** internal/admin — `POST /api/media-cases/` (flag new item), `PATCH /api/media-cases/{id}/classify/`, `PATCH /api/media-cases/{id}/status/`, `POST /api/media-cases/{id}/response/`, `GET /api/media-cases/trends/?by=source|keyword|date` (Admin/Editor only); public — `GET /api/media-cases/public/?theme=&source=&from=&to=`, `GET /api/media-cases/public/{id}/` (both strictly filtered to `status=public`).

## Testing Decisions

Deferred — no code yet. This module's single most important test, once built: no `MediaCase` reaches any public-facing endpoint unless its status is exactly `public` (confirmed classification + published response) — test this before anything else, including trend-dashboard correctness, since a leak here has direct reputational/legal risk (publishing an unconfirmed accusation of e.g. hate speech).

## Out of Scope

- Automated detection/classification (ML-based flagging of misinformation) — flagging and classification are manual/editorial per the source doc, not automated.
- Public commenting or dispute-submission on published cases — not mentioned in the source doc.
- Legal review workflow beyond standard Editor confirmation — not specified; if PRI needs formal legal sign-off before publishing sensitive classifications (e.g. "hate speech" against a named source), that should be raised as a real requirement before this module is built, not assumed away.

## Further Notes

- Source: docx Backend §2.E "Media Watch & Rapid Response Module" — "Upload and tag media items (images, headlines, videos); Classify: Hate speech, misinformation, communal bias, etc.; Internal review flagging system; Dashboard for tracking trends (by source, keyword, date); Archive system with filters."
- The two-part public-release gate here (classification confirmed + response published) is the same visibility-discipline pattern used in [Module C](C-data-repository-dashboard-integration.md) (dataset visibility tiers) — apply the same testing rigor.
