# Spec: Backend Module G — Forms, Surveys, and Contact Management

**Backend module G** · Status: Drafted · Future phase — not yet prioritized for build · Feeds: [Partner & Consortium Network](../frontend/08-partner-consortium-network.md), [Events & Campaigns](../frontend/10-events-campaigns.md), [Get Involved](../frontend/11-get-involved.md), [Contact & Newsletter](../frontend/12-contact-newsletter.md) · Depends on: none directly

## Problem Statement

At least seven different frontend forms across the site (newsletter signup, volunteer, intern-interest, event registration, media/research/general contact, partnership forms, suggestions, whistleblower) currently have nowhere to submit to — without one consistent, secure form-handling backend, each would need its own ad hoc storage, spam protection, and routing logic, multiplying effort and creating inconsistent security/reliability across the site's most direct visitor-to-PRI touchpoints.

## Solution

A single, general-purpose forms and contact-management module: configurable form definitions, secure submission storage with export capability, CAPTCHA and rate-limiting, category-based email routing to the correct department, and CRM integration (Airtable/Zoho) — used as the shared backend for every form-based interaction across the site.

## User Stories

1. As an Admin, I want to define a new form (fields, required/optional, routing destination) without a code deployment, so that new forms (e.g. a new campaign's sign-up) can be added quickly.
2. As a visitor, I want my form submission protected by CAPTCHA, so that I'm confident the system isn't overwhelmed by spam/bots.
3. As an Admin, I want submission rate-limiting per visitor/IP, so that the system is resistant to abuse or accidental duplicate flooding.
4. As an Admin, I want each form's submissions routed by email to the correct department based on the form (or a field within it, e.g. contact-form category), so that inquiries reach the right people automatically.
5. As an Admin, I want to export a form's submissions (e.g. as CSV), so that I can analyze or archive them outside the system.
6. As an Admin, I want submissions synced to a CRM (Airtable API or Zoho CRM), so that donor/partner/fellow-adjacent contacts feed into PRI's broader relationship-management tooling.
7. As an Admin, I want the whistleblower form (per Get Involved, §11) to support true anonymous submission with no identifying metadata stored, so that this module's general submission-storage pattern has an explicit anonymous exception.
8. As an Admin, I want newsletter sign-ups tagged by segment (general, donor, media), so that a single mailing-list mechanism serves every page that offers a newsletter/briefing sign-up.
9. As an event organizer (internal), I want event-registration submissions tied to a specific event with auto-confirmation, so that registration works as its own form type within this shared system.
10. As an Admin, I want a way to see submission volume/status per form, so that I can monitor whether forms are functioning (e.g. detect if a form suddenly gets zero submissions, suggesting a bug).
11. As a developer integrating a new frontend page, I want a consistent API pattern for submitting to any form (`POST /api/forms/{form_slug}/`), so that adding a new form to the site doesn't require inventing a new backend pattern each time.
12. As an Admin, I want form data encrypted at rest and access-limited by role, so that submitted personal information (especially from the whistleblower and donor-adjacent forms) is protected per the project's security baseline.

## Implementation Decisions

- **Data model:** `FormDefinition` (slug, name, field schema, routing rule, CRM-sync flag, anonymous-allowed flag), `FormSubmission` (form FK, submitted data — as structured JSON matching the field schema, submitted_at, submitter metadata unless `anonymous_allowed` and the submitter opted in, in which case metadata is omitted entirely, not merely hidden).
- **One generic engine, many form instances:** rather than a bespoke backend per form type (contact, volunteer, whistleblower, event registration, newsletter, partnership, suggestion), all are `FormDefinition` instances of one engine — matches the pattern every dependent frontend spec (§8, §10, §11, §12) already assumes.
- **Routing:** each `FormDefinition` has a routing rule — either a fixed destination, or (for the Contact form) a rule keyed off a specific field value (e.g. `category=research|media|general` → different destination per value).
- **Anonymity handling:** `anonymous_allowed` forms (the whistleblower form specifically) must strip identifying metadata (name/email/IP/session) at the storage layer when the submitter opts in — this is a hard requirement carried over from the [Get Involved](../frontend/11-get-involved.md) spec, not an optional nicety; it should also exclude such submissions from any bulk-export or CRM-sync path by default, since those paths assume identifiable data.
- **Newsletter as a form type:** signup is itself a `FormDefinition` (segment tag as a field), consistent with every page that offers a newsletter/briefing sign-up ([Contact & Newsletter](../frontend/12-contact-newsletter.md), [Donors Forum](../frontend/09-donors-sponsors-forum.md), [Get Involved](../frontend/11-get-involved.md)) pointing at the same underlying mechanism.
- **Event registration as a form type:** `FormDefinition` with a required `event_id` reference and an auto-confirmation action (email/on-screen) fired synchronously on submission, per [Events & Campaigns](../frontend/10-events-campaigns.md)'s explicit requirement.
- **API surface:** `POST /api/forms/{form_slug}/` (generic submission endpoint, validated against that form's field schema), `GET /api/forms/{form_slug}/submissions/?export=csv` (Admin-only, respects anonymity exclusions), CRM-sync is an async side-effect on submission (webhook/queued job to Airtable/Zoho), not part of the synchronous request path.

## Testing Decisions

Deferred — no code yet. Given this module is shared infrastructure for many frontend sections, prioritize testing: (1) routing correctness per form/category — a misrouted submission is effectively lost, (2) the anonymity guarantee for `anonymous_allowed` forms end-to-end (storage layer, export, CRM sync all correctly exclude identifying data), and (3) CAPTCHA/rate-limiting actually blocking abusive submission patterns. These three are higher priority than form-builder UI convenience.

## Out of Scope

- Building the CRM itself (Airtable/Zoho) — this module integrates with an existing CRM via API, doesn't replace one.
- Survey logic beyond simple form submission (branching/conditional questions, multi-page surveys) — the source doc's "Forms, Surveys" framing doesn't specify advanced survey logic; treat as flat forms unless a specific future section needs more.
- Marketing-automation/email-campaign sending (Mailchimp/ConvertKit, per the source doc's general integrations list) — this module handles sign-up capture and segmentation tagging, not the sending pipeline.

## Further Notes

- Source: docx Backend §2.G "Forms, Surveys, and Contact Management" — "Forms for: Newsletter signup, volunteer, event registration, media contact, feedback; Secure data storage with export capability; CAPTCHA, rate-limiting, and email routing to respective departments; CRM Integration (e.g., Airtable API / Zoho CRM)."
- This module is a dependency of more Phase-2+ frontend sections than any other backend module (§8, §10, §11, §12, plus feedback forms referenced in §5 and §9) — reasonable to prioritize building it early in the next phase given how many sections are blocked on it.
- The anonymity requirement here is a direct carry-over from [Get Involved](../frontend/11-get-involved.md)'s whistleblower-form user story — treat that spec's framing as authoritative if the two ever seem to conflict.
