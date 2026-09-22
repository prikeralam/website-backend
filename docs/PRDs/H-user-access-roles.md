# Spec: Backend Module H — User Access & Roles

**Backend module H** · Status: Drafted · Future phase — not yet prioritized for build, but see Further Notes on why it should be pulled earlier · Feeds: every other module (A–G) · Depends on: none (foundational, cross-cutting)

## Problem Statement

Modules A and C (already specced for Phase 1) each independently define a version of role-based access — Admin/Editor/Researcher/Intern-Fellow/Donor-Visitor permissions — because no single, authoritative permission system exists yet. Left unaddressed, every subsequent module (B, D, E, F, G) will either re-derive the same role logic slightly differently, or drift into inconsistent enforcement, creating exactly the kind of security gap (a role that should be blocked from something isn't, because two modules implemented "the same" rule differently) that the project's security baseline is meant to prevent.

## Solution

A single, authoritative role/permission system defining the five site-wide roles (Admin, Editor, Researcher, Intern/Fellow, Donor/Visitor) and their permissions, that every other module's authorization checks call into — rather than each module reimplementing its own role logic.

## User Stories

1. As an Admin, I want full access to every module (content, data, applications, media cases, donations, forms), so that I can administer the whole platform from one account type.
2. As an Editor, I want permission to approve/publish content and upload research across every module that has a Draft→Review→Approve→Publish workflow (A, B, and by extension the CMS-backed parts of E, F reports), so that editorial control is consistent everywhere, not module-by-module.
3. As a Researcher, I want permission to draft research entries and upload datasets (Modules A, B, C, E), so that my contribution rights are consistent across every content-producing module.
4. As an Intern/Fellow, I want permission to submit work and view only pages assigned to me (relevant to Module D's applicant/fellow flows), so that my access is appropriately narrow.
5. As a Donor/Visitor, I want limited access — downloads, forms, and donation actions only — with no access to any draft/internal content across any module, so that the public-facing boundary is enforced consistently everywhere, not just in the modules that happened to think about it.
6. As a developer implementing a new module (e.g. Module D or F), I want to call a shared permission-check function/decorator rather than writing new role logic, so that my module automatically inherits the correct, tested rules.
7. As an Admin, I want to see an audit log of permission-relevant actions (who published what, who approved which access request, who changed a status) across all modules in one place, so that accountability isn't scattered per-module.
8. As an Admin, I want to grant or revoke a user's role, so that staffing changes (a new Editor, a departing Researcher) take effect immediately across every module at once.
9. As a Reviewer (Module D-specific reviewer role for selection committees), I want to understand how my role relates to the five site-wide roles, so that Module D's reviewer permission isn't an unexplained one-off outside this system.
10. As a security-conscious Admin, I want role checks enforced server-side on every endpoint across every module (not just in the frontend UI), so that permission logic can't be bypassed by calling the API directly.

## Implementation Decisions

- **This module is the authoritative source; Modules A and C should be treated as early, consistent implementations of it, not competitors to it.** Concretely: extract the role/permission logic already described in A's and C's specs into one shared mechanism (e.g. a Django permissions/group scheme, or a custom role-check decorator/middleware used by every app), and have A and C's actual implementation depend on this module rather than duplicating role checks — this is a refactor-at-build-time note, not a spec conflict, since both specs were written role-consistent with this one.
- **Five site-wide roles** (Admin, Editor, Researcher, Intern/Fellow, Donor/Visitor), matching the project CLAUDE.md's roles table exactly — this spec is the canonical definition; CLAUDE.md's table should be read as a summary of this spec, not a separate source of truth.
- **Module-specific sub-roles (e.g. Module D's "Reviewer") are modeled as an extension/annotation on top of the five base roles**, not a sixth site-wide role — e.g. a user might hold the Editor role plus a Reviewer flag scoped to a specific `Program`, rather than "Reviewer" being a global role with its own independent meaning.
- **Enforcement point:** permission checks live at the API boundary (every DRF view/endpoint across every module authorizes via this shared mechanism), consistent with the API-boundary testing philosophy already established in Modules A and C's specs.
- **Cross-cutting audit log:** a shared `AuditLogEntry` model (actor, action, target module/object, timestamp) that any module can write to, rather than each module maintaining a separate audit trail — makes Admin's "one place to see everything" story (User Story 7) possible.
- **API surface:** this module is mostly infrastructure other modules call into rather than a set of its own public endpoints, but it does need: `GET /api/users/me/role/` (a user checking their own permissions, useful for frontend conditional rendering), Admin-only `PATCH /api/users/{id}/role/` (grant/revoke), `GET /api/audit-log/?module=&actor=` (Admin-only, cross-module).

## Testing Decisions

Deferred — no code yet, but this module's tests are the highest-leverage tests in the whole project once it exists: a bug here potentially affects every other module simultaneously. When built, test the permission matrix exhaustively (every role × every cross-module action it should/shouldn't be able to do) before testing anything module-specific, and require every new module's spec/PR to state which of this module's checks it uses rather than inventing its own.

## Out of Scope

- Fine-grained, per-object ACLs beyond the five-role model (e.g. "this specific Researcher can only edit this specific dataset") — the source doc's role table is coarse-grained (module-level permissions per role), not object-level; revisit only if a real need emerges.
- Single sign-on / external identity-provider integration — not mentioned in the source doc; assume PRI's own account system unless specified otherwise.
- Public user self-registration flows for non-donor roles (Editor/Researcher/Admin accounts are presumably provisioned internally, not self-service signups) — only Donor/Visitor-tier accounts are self-service, per the pattern implied across the other specs (e.g. Module C's dataset-access requesters, Module F's donors).

## Further Notes

- Source: docx Backend §2.H "User Access & Roles" — table: "Admin: Full access to all modules; Editor: Approve/publish content, upload research; Researcher: Draft research entries, upload datasets; Intern/Fellow: Submit work, view assigned pages; Donor/Visitor: Limited access (downloads, forms, donation)." This is presented in the source doc as a permissions table, not a feature list like A–G, which is why this spec is framed around the permission system itself rather than a user-facing feature.
- **Recommendation for prioritization (not a decision made here, just flagged for the next planning pass):** because Modules A and C (Phase 1) already implement role logic ad hoc per their own specs, and every future module (B, D, E, F, G) will need the same logic, there's a real argument for building Module H's shared mechanism early — ideally alongside or immediately after Module A — rather than leaving it last alphabetically. Raise this with the user when re-prioritizing beyond Phase 1.
