# Spec: Backend Module D — Fellowship / Internship Management System

**Backend module D** · Status: Drafted · Future phase — not yet prioritized for build · Feeds: [Fellowship & Internship Portal](../frontend/05-fellowship-internship-portal.md) · Depends on: [Module A — CMS](A-content-management-system.md) (fellow profiles)

## Problem Statement

Without a dedicated system, fellowship/internship applications have no structured intake, no way for a selection committee to review and compare candidates efficiently, and no automated status communication — applicants are left wondering where they stand, and reviewers have to track everything manually (spreadsheets, email threads), which doesn't scale as application volume grows.

## Solution

An application management system with a configurable form builder and document upload, a filterable applicant database with status tracking, a reviewer dashboard for selection committees, automated status emails at each stage, and a link from approved fellows into their public profile pages.

## User Stories

1. As an Admin, I want to configure an application form (fields, required documents) per program/cycle using a form builder, so that different fellowship programs can have different application requirements without a code change.
2. As an applicant, I want to submit an application with document uploads (CV, writing sample, etc.), so that I can apply fully online.
3. As an applicant, I want automatic confirmation once I submit, so that I know my application was received.
4. As a Reviewer, I want to browse and filter the applicant database (by program, status, submission date), so that I can efficiently work through a review cycle.
5. As a Reviewer, I want to score or annotate an application, so that the selection committee has a shared basis for decisions.
6. As a Reviewer, I want to change an applicant's status (e.g. under review, shortlisted, rejected, accepted), so that the pipeline reflects real progress.
7. As an applicant, I want to automatically receive an email when my status changes (shortlisted, rejected, onboarding), so that I'm kept informed without needing to check back.
8. As an Admin, I want an onboarding step for accepted applicants that creates or links their public fellow profile (Module A `PersonProfile`), so that accepted fellows appear on the public portal without manual duplicate data entry.
9. As an Admin, I want role-gated access so only Reviewers/Admins can see applicant data, so that sensitive personal information isn't broadly exposed.
10. As a Reviewer, I want to see multiple reviewers' input on the same application (if the committee has more than one reviewer), so that decisions reflect a full committee view, not just one person's read.
11. As an Admin, I want an audit log of status changes and who made them, so that decisions are traceable if questioned later.
12. As a developer building the Fellowship Portal frontend, I want a stable API for program/timeline data and application submission, so the public form can be built against an agreed contract.

## Implementation Decisions

- **Data model:** `Program` (name, description, timeline/dates, active status), `ApplicationForm` (per-program configurable field schema — form-builder-driven, not hardcoded), `Application` (applicant info, submitted answers, uploaded documents, status: submitted/under_review/shortlisted/rejected/accepted/onboarded, program FK), `Review` (application FK, reviewer FK, score/notes — supports multiple reviews per application), status-change triggers an `Email` send keyed to the new status.
- **Form builder:** configurable field schema per `Program` (field name, type, required, document-upload flag) rather than one fixed application shape — matches the doc's explicit "Application form builder" language and supports different requirements across fellowship vs. internship programs.
- **Status-driven auto-emails:** implemented as a status-transition hook (status change → look up template for new status → send) rather than manually triggered per-application, so no status change is silently missed.
- **Fellow profile linking:** on transition to `onboarded`, the system creates or updates a Module A `PersonProfile` (group="fellow") from the application's data — a one-way sync at onboarding time, not a live-linked record, so profile edits after onboarding are managed normally through Module A.
- **Access control:** `Application` and `Review` records are Reviewer/Admin-only; Intern/Fellow role (per the site-wide role table) can view only their own submitted application status, not others'.
- **API surface:** `GET /api/programs/` (public, feeds portal overview), `POST /api/applications/` (public submission), `GET /api/applications/me/` (applicant's own status, authenticated), `GET /api/applications/?program=&status=` (Reviewer/Admin only, filtered dashboard), `POST /api/applications/{id}/reviews/` (Reviewer submits review), `PATCH /api/applications/{id}/status/` (Reviewer/Admin, triggers auto-email).

## Testing Decisions

Deferred — no code yet. The status-transition → auto-email pipeline is the core guarantee of this module (an applicant must be notified correctly and only for their own status changes) — prioritize testing that over dashboard filtering mechanics. Also test that `Application`/`Review` data is genuinely inaccessible to non-Reviewer/Admin roles, mirroring the access-control testing discipline established in [Module C](C-data-repository-dashboard-integration.md).

## Out of Scope

- Interview scheduling — not mentioned in the source doc; assume review happens on submitted materials only unless told otherwise.
- Payroll/stipend administration for accepted fellows — not specified.
- Multi-round application processes (e.g. written round then interview round) beyond the single status pipeline described — revisit if PRI's actual process needs more stages.

## Further Notes

- Source: docx Backend §2.D "Fellowship / Internship Management System" — "Application form builder + upload fields; Applicant database with filtering & status tracking; Reviewer dashboard for selection committees; Auto-emails: confirmation, shortlisting, rejection, onboarding; Fellow profile pages with publication links."
- "Fellow profile pages with publication links" ties this module to [Module B](B-publication-repository-module.md) via the shared `PersonProfile` — once a fellow is onboarded and later authors publications, the link is automatic through that shared model, not a separate integration.
- **Needs stakeholder clarification** (carried from [Get Involved](../frontend/11-get-involved.md)'s spec): whether this module's application intake is the same pipeline used by the Get Involved page's "intern form," or a separate, lighter-weight one. Resolve before building.
