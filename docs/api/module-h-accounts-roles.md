# Module H — Users, Roles & Audit Log

Source PRD: `docs/PRDs/H-user-access-roles.md`. See [README.md](README.md) for auth, permission matrix, and pagination conventions shared across all modules.

Per PRD H's own framing (line 28), this module is mostly infrastructure other modules call into (the shared `WorkflowMixin`/`CanSubmitDraft`/`CanTransitionStatus` mechanism in `apps/workflow/`, documented in [README.md](README.md#permission-matrix-module-h-authoritative--see-module-h-doc)) rather than a large surface of its own endpoints.

## Endpoints

| Method & Path | Auth | Description | Status |
|---|---|---|---|
| `POST /api/v1/token/`, `/token/refresh/`, `/token/logout/` | Anonymous | Sign in (throttled 5/min per username, `429` beyond), renew the access token, sign out (blacklists the refresh token). See [README.md](README.md#authentication). | **Built** — `LoginView`/`LogoutView`, `apps/accounts/views.py` |
| `GET /api/v1/users/me/role/` | Authenticated | Current user's id/email/role, for frontend conditional rendering. | **Built** — `MyRoleView`, `apps/accounts/views.py:17` |
| `PATCH /api/v1/users/{id}/role/` | Admin only | Grant/revoke a user's role. Writes an `AuditLog` row (`module="accounts"`, `action="role_change"`). | **Built** — `UserRoleUpdateView`, `apps/accounts/views.py:25` |
| `GET /api/v1/audit-log/?module=&actor=` | Admin only | Cross-module audit trail, filterable by module and actor. | **Built** — `AuditLogListView`, `apps/accounts/views.py:53` |

## Request/response shapes (built endpoints)

**`GET /users/me/role/`**
```json
{"id": 1, "email": "user@example.com", "role": "editor"}
```
Serializer: `MyRoleSerializer` (`apps/accounts/serializers.py`).

**`PATCH /users/{id}/role/`**
Request: `{"role": "editor"}`
Response: same shape as `MyRoleSerializer`, for the target user.

**`GET /audit-log/`**
```json
[{"id": 1, "actor": 1, "module": "content", "action": "status_transition", "target": "contentblock:4", "metadata": {"previous_status": "draft", "new_status": "in_review"}, "timestamp": "2026-09-21T10:00:00Z"}]
```
Serializer: `AuditLogSerializer` (`apps/accounts/serializers.py`). Currently unpaginated (see [README.md](README.md#pagination)).

## Gap — flagged, not filled

There is no endpoint to list or search users. `PATCH /users/{id}/role/` requires knowing a target `{id}` in advance, but nothing in the API surfaces user IDs (only Django admin does). This needs a decision (e.g. `GET /api/v1/users/?role=&q=`, admin-only) before an admin UI can realistically call the role-update endpoint. Not drafted here since no PRD names this endpoint explicitly — flagging for confirmation rather than inventing it.

## Explicitly excluded from this v1 contract

Per `docs/erd/README.md:121,123`, both of these are labeled "recommended addition, no PRD names them" — not drafted as endpoints here, consistent with not building ahead of a named requirement:

- `accounts_apikey` (per-user API keys for programmatic access) — confirmed only in the live prototype's mock account dashboard, no backend PRD requests it.
- `accounts_notificationlog` (auto-email delivery log) — implied by Modules D/F/G's auto-email requirements, but those modules are out of scope for this pass anyway.

## Role enum (reference)

`apps/accounts/models.py:5-10` — `Role` TextChoices: `public` (Donor/Visitor), `researcher`, `editor`, `fellow` (Intern/Fellow), `admin`. Deliberately matches the companion Next.js frontend's mock-auth `Role` type values (per backend CLAUDE.md's Architectural Decisions), including using `public` rather than `donor` for that reason.
