# Spec: Backend Module F — Donor & Fundraising Backend

**Backend module F** · Status: Drafted · Future phase — not yet prioritized for build · Feeds: [Donors & Sponsors Forum](../frontend/09-donors-sponsors-forum.md) · Depends on: none directly, but shares document/report handling with [Module A — CMS](A-content-management-system.md)

## Problem Statement

PRI cannot currently accept online donations, track who has given what, issue tax receipts, or give donors any self-service view of their giving and its impact — all fundraising is presumably manual/offline, which caps how much PRI can raise online and creates real overhead (manual receipt generation, no donor record system) as giving grows.

## Solution

A donor and fundraising backend handling donor registration, donation tracking, payment-gateway integration (Razorpay/Instamojo), auto-generated tax receipts, a donor-facing dashboard for reports and impact materials, and an admin backend for uploading reports, setting donation tiers, and monitoring campaigns.

## User Stories

1. As a donor, I want to make a donation through an integrated payment gateway (Razorpay or Instamojo), so that I can give directly on the site.
2. As a donor, I want an account created (or linked) when I donate, so that my giving history is tracked over time.
3. As a donor, I want an automatically generated tax receipt after a successful donation, so that I have documentation for tax purposes without requesting it manually.
4. As a donor, I want to log into a donor dashboard and see my donation history, reports, and impact materials, so that I have self-service access without contacting PRI directly.
5. As an Admin, I want to set donation tiers (e.g. suggested amounts or named giving levels), so that the donation flow reflects current fundraising strategy.
6. As an Admin, I want to monitor active campaigns (donations received, progress toward a goal), so that I can track fundraising performance.
7. As an Admin, I want to upload annual funder reports and impact materials to be shown in the donor dashboard and/or the public Donors Forum, so that transparency materials stay current.
8. As an Admin, I want donation records to reconcile reliably with payment-gateway transaction records, so that financial reporting is accurate.
9. As a donor, I want to be notified my payment succeeded (or clearly told if it failed), so that I'm never left uncertain about whether my donation went through.
10. As an Admin, I want donor personal and payment data handled securely (per the project's security baseline — encrypted storage, no exposure of raw payment details), so that PRI meets its data-protection obligations for financial information.
11. As a developer building the Donors & Sponsors Forum frontend, I want a stable API for initiating a donation, checking status, and fetching impact metrics/named-program data, so the frontend can be built against an agreed contract.

## Implementation Decisions

- **Data model:** `Donor` (linked user account, name, contact info), `Donation` (donor FK, amount, currency, campaign FK optional, payment_gateway_ref, status: pending/succeeded/failed, created_at), `TaxReceipt` (donation FK, generated_at, file), `DonationTier` (label, suggested amount, admin-managed), `Campaign` (name, goal amount, active dates, progress = aggregate of linked `Donation`s).
- **Payment flow:** frontend initiates a `Donation` (pending) → redirects to/embeds Razorpay or Instamojo → gateway webhook confirms success/failure → `Donation.status` updated → on success, `TaxReceipt` auto-generated and donor notified. Webhook-driven status update (not client-reported) is the correct source of truth, since a client-side "success" claim is not trustworthy for financial records.
- **Tax receipts:** auto-generated as a PDF from `Donation` + `Donor` data immediately on confirmed success, stored and retrievable from the donor dashboard — not manually triggered by staff, to avoid delay/error.
- **Donor dashboard access:** `Donor` accounts are a distinct authenticated role (extends the site-wide Donor/Visitor role from [Module H](H-user-access-roles.md)) scoped to their own `Donation`/`TaxReceipt` records only.
- **Reports/impact materials:** reuses Module A's `Document` type (same mechanism as About PRI's annual reports) tagged for donor/public visibility, rather than a separate document system in this module.
- **API surface:** `POST /api/donations/` (initiate, returns gateway redirect/embed info), `GET /api/donations/{id}/status/` (poll/confirm), webhook endpoint for gateway callbacks (not public-facing, gateway-authenticated), `GET /api/donors/me/donations/` (donor dashboard, authenticated), `GET /api/donors/me/receipts/{id}/` (receipt download), `GET /api/campaigns/?active=true` (public, for impact metrics/progress), admin endpoints for tiers/campaigns/report uploads (shape deferred to build time).

## Testing Decisions

Deferred — no code yet. This module handles real money, so once built: prioritize testing that `Donation.status` only ever becomes `succeeded` from an authenticated gateway webhook (never from a client-reported call), that a `TaxReceipt` is only generated for genuinely succeeded donations, and that a donor can only ever see their own records — these three guarantees matter more than UI polish or campaign-progress display logic.

## Out of Scope

- Recurring/subscription donations — not specified in the source doc (flagged as an open question in the Donors Forum frontend spec too); one-time donations only unless confirmed otherwise.
- CRM sync (Zoho/Airtable, per the source doc's general "Optional Integrations") — worth wiring once this module exists, but not part of the core module build.
- Multi-currency handling beyond whatever Razorpay/Instamojo natively support — no separate currency-conversion logic assumed.
- Refund processing — not mentioned in the source doc; would need explicit scoping before building if required.

## Further Notes

- Source: docx Backend §2.F "Donor & Fundraising Backend" — "Donor registration and donation tracking; Integration with payment gateways (Razorpay, Instamojo); Auto-generated tax receipts; Donor dashboard to access reports and impact materials; Admin backend to upload reports, set donation tiers, monitor campaigns."
- Report/document handling reuses [Module A](A-content-management-system.md)'s `Document` type — same pattern as [About PRI](../frontend/02-about-pri.md)'s annual reports; don't build a parallel document system here.
- Donor role extends the site-wide role table owned by [Module H](H-user-access-roles.md) — this module should conform to H's permission model once H exists, not define its own separate role concept.
