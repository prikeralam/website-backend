# Spec: Backend Module A — Content Management System

**Backend module A** · Status: Drafted · Feeds: [Homepage](../frontend/01-homepage.md), [About PRI](../frontend/02-about-pri.md) · Depends on: none (foundational module)

## Problem Statement

Every frontend page in this project — starting with the Homepage and About PRI, and every future content-heavy section — needs editorially-managed content (mission copy, testimonials, governance listings, documents, "latest updates" feeds) that non-developers (Editors, Researchers, Comms staff) can create and change without a code deployment. Without a CMS, either every content change requires a developer, or content gets hardcoded into the frontend and drifts out of date — neither is acceptable for an institution whose credibility depends on an accurate, current public presence.

## Solution

A modular, role-based content management system in Django that supports multiple content types (generic content blocks, testimonials, person/role profiles, documents/media, and a queryable "latest updates" feed spanning content types), a fixed editorial workflow (Draft → Review → Approve → Publish), Markdown or WYSIWYG authoring, and SEO meta-tagging — exposed via a REST API (Django REST Framework, pending the open Django/FastAPI decision) that the Next.js frontend consumes.

## User Stories

1. As a Researcher, I want to draft a new content entry (e.g. a page content block or document) in Markdown or a WYSIWYG editor, so that I don't need to know HTML/code to contribute.
2. As a Researcher, I want my draft to enter a Review state rather than going live immediately, so that inaccurate or unapproved content can't reach the public site.
3. As an Editor, I want to review and either approve or send back drafts submitted by Researchers, so that I control what gets published under PRI's name.
4. As an Editor, I want to publish an approved draft, so that it becomes visible on the live site.
5. As an Editor, I want to un-publish or edit already-published content, so that I can correct errors or retire outdated material without developer involvement.
6. As an Editor, I want to add SEO meta-tags (title, description) to a content entry, so that it's discoverable via search engines.
7. As a Comms Coordinator, I want to create and edit "testimonial" entries (quote, author name, role/affiliation, optional photo), so that the homepage (and later, other pages) can display social proof.
8. As a Comms/Admin staff member, I want to create and edit "person/role" profiles (name, role, council/affiliation, optional bio/photo) for governance members, so that the About PRI page's governance section stays current.
9. As an Editor, I want to upload a document (e.g. an annual report PDF) with metadata (title, year, type) and put it through the same Draft→Review→Approve→Publish workflow, so that document publishing follows the same controls as other content.
10. As a frontend developer/consumer, I want a "latest updates" API endpoint that returns the most recently published content across types (ordered by publish date, filterable), so that the Homepage can render a live activity feed without a bespoke backend for it.
11. As an Admin, I want role-based permissions enforced server-side (Admin/Editor/Researcher can create, review, approve, publish per their role; Intern/Fellow and Donor/Visitor cannot), so that unauthorized users can't alter or publish site content.
12. As an Admin, I want an activity/audit trail of who created, reviewed, approved, and published each piece of content, so that I can trace accountability if something incorrect goes live.
13. As a developer building the Homepage or About PRI pages, I want a stable REST API contract for content blocks (by slug), testimonials (list), person/role profiles (list, filterable by council), and documents (list, filterable by type/year), so that frontend and backend can be built against an agreed interface.

## Implementation Decisions

- **Content types (initial set, driven by Phase 1 frontend needs):**
  - `ContentBlock` — slug-addressable prose/rich-text block (hero copy, Director's Note, institutional overview, quick-link labels). Fields: slug, title, body (Markdown or WYSIWYG-stored HTML), SEO meta title/description, status, timestamps.
  - `Testimonial` — quote, author name, author role/affiliation, optional photo, status.
  - `PersonProfile` — name, role/title, group (e.g. "Executive Council", "Steering Council" — extensible enum/tag, not hardcoded to governance only, since the source doc also implies author profiles for researchers in a future phase), optional bio, optional photo, status.
  - `Document` — title, file (PDF), type (e.g. "Annual Report", "Strategic Plan"), year, status.
  - Each content type shares the same workflow state machine and audit fields (see below) rather than each reinventing it — implemented as a shared abstract base/mixin at the model level.
- **Workflow state machine (shared across all content types):** `Draft → In Review → Approved → Published`, plus an `Unpublished`/archived end state reachable from `Published`. Transitions are role-gated: Researcher can move Draft→In Review; Editor/Admin can move In Review→Approved→Published, and Published→Unpublished.
- **Roles enforced server-side**, matching the site-wide table in the project CLAUDE.md: Admin (full access), Editor (approve/publish/upload), Researcher (draft/upload), Intern/Fellow (submit/view assigned — not exercised by this module's content types in Phase 1), Donor/Visitor (read-only, published content only).
- **Authoring format:** Markdown stored as source-of-truth for `ContentBlock.body`; WYSIWYG editor in the admin UI is a presentation layer over the same Markdown field, not a separate storage format — avoids format drift.
- **SEO meta-tagging:** meta title/description fields on every publishable content type, defaulting to derived values (e.g. truncated body) if left blank.
- **API surface (DRF, pending open framework decision):**
  - `GET /api/content-blocks/{slug}/` — single published block by slug (Homepage hero, About PRI overview/Director's Note).
  - `GET /api/testimonials/` — list of published testimonials.
  - `GET /api/people/?group=` — list of published person profiles, filterable by group (governance council, etc.).
  - `GET /api/documents/?type=&year=` — list of published documents, filterable.
  - `GET /api/updates/latest/?limit=&types=` — cross-type feed of most recently published content, ordered by publish date, optionally filtered by content type — powers the Homepage "Latest Updates" section.
  - Write endpoints (create/update/transition) are role-gated and used by an internal admin UI, not the public frontend — exact write-endpoint shapes are an implementation detail for the build phase, not fixed here.
- **Person model question (carried over from About PRI spec):** `PersonProfile.group` is a tag/enum field precisely so governance members and (future) research-author profiles can share one model instead of forking into two — resolves the open question raised in About PRI's spec.

## Testing Decisions

Deferred in detail (no code yet), but since this is the foundational module, its testing approach sets the pattern for everything downstream: prefer testing at the API boundary (DRF endpoint behavior: correct filtering, correct role-based access, correct workflow-transition rules) over testing internal implementation details, since the frontend only ever interacts through that boundary. Workflow state-machine transitions (who can move what, from where, to where) are the highest-value thing to test given they're the module's core guarantee. Revisit and finalize once the Django project scaffold exists.

## Out of Scope

- Publication Repository Module (B) — separate module for research papers/publications with citation export, DOI/slug, versioning; this module (A) only covers generic content blocks, testimonials, person profiles, and simple documents.
- Data Repository & Dashboard Integration (Module C) — datasets, visualizations, maps are a separate module (spec follows this one).
- Fellowship application forms, media-watch tagging, donor/payment processing, surveys — all future-phase modules (D, E, F, G) with their own content needs, not built here.
- Multi-language content storage strategy (EN/Malayalam) — flagged as an open dependency from the Homepage/About PRI specs; not resolved in this pass. Recommend deciding before building `ContentBlock` if i18n is needed at launch, since it affects the model shape (single field with a language variant vs. separate localized rows).
- Full CI/CD, hosting, and deployment setup — covered by project-level setup, not this module's spec.

## Further Notes

- Source: docx Backend §2.A "Content Management System" — "Blog posts, publication pages, landing pages; Role-based publishing (Editor, Researcher, Comms); Markdown + WYSIWYG support; Meta-tagging for SEO and discoverability; Workflow: Draft → Review → Approve → Publish."
- This spec deliberately scopes down from "blog posts, publication pages, landing pages" (the doc's broader framing) to the concrete content types the Phase 1 frontend pages (Homepage, About PRI) actually need. Broaden the content-type set when Publication Repository (Module B) or the Research & Publications Hub (§3) get specced.
- **Open decision carried from CLAUDE.md:** whether this module is pure Django+DRF or gains a FastAPI component. Nothing above assumes either way beyond "a REST API exists" — the endpoint list is framework-agnostic and should hold regardless of which is chosen.
