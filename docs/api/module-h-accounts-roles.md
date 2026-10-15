# Module H — Users, Roles & Audit Log

Source PRD: `docs/PRDs/H-user-access-roles.md`. See [README.md](README.md) for auth, permission matrix, and pagination conventions shared across all modules.

Per PRD H's own framing (line 28), this module is mostly infrastructure other modules call into (the shared `WorkflowMixin`/`CanSubmitDraft`/`CanTransitionStatus` mechanism in `apps/workflow/`, documented in [README.md](README.md#permission-matrix-module-h-authoritative--see-module-h-doc)). On top of that it exposes admin user management (issue #38), so the frontend can run an admin UI without Django admin.

Access is **per role, not per user**: "giving a user access" means setting their role. Per-user dataset access is Module C's access-request flow. Decisions behind this API are recorded in issue #38.

## Endpoints

| Method & Path | Auth | Description |
|---|---|---|
| `POST /api/v1/token/`, `/token/refresh/`, `/token/logout/` | Anonymous | Sign in (throttled 5/min per username, `429` beyond), renew the access token, sign out (blacklists the refresh token). See [README.md](README.md#authentication). |
| `POST /api/v1/token/google/` | Anonymous | Sign in with Google: `{credential}` (the ID token from Google Identity Services) for the same `{access, refresh}` as `/token/`. The token must be RS256-signed by Google for `GOOGLE_CLIENT_ID`, unexpired, with `email_verified`. An active account whose email or username matches is signed in (an unconfirmed self-registered visitor account loses its password and sessions first, since Google proves who owns the address); otherwise a confirmed visitor account with no password is created (`user.registered`, `via: google`). `401` for a token it can't accept or a deactivated account, `503` when Google's keys can't be fetched, `404` while `GOOGLE_CLIENT_ID` is unset; 300/hour in total. |
| `GET /api/v1/users/me/role/` | Authenticated | Current user's id/email/role, for frontend conditional rendering. |
| `GET`, `PATCH /api/v1/users/me/` | Authenticated | Own profile. `PATCH` accepts `email`, `first_name`, `last_name` only. |
| `POST /api/v1/users/me/password/` | Authenticated | `{"old_password", "new_password"}` → `204`. Clears `must_change_password`. |
| `GET /api/v1/users/?role=&is_active=&q=` | Admin | Paginated, ordered by username. `q` matches username, email, first and last name. |
| `GET /api/v1/users/{id}/` | Admin | One user. |
| `POST /api/v1/users/` | Admin | Create. With `password`: a temporary password (`must_change_password` set). Without: an unusable password and an invite email. `201`. |
| `PATCH /api/v1/users/{id}/` | Admin | `email`, `first_name`, `last_name` only. Other fields in the body are ignored. |
| `POST /api/v1/users/{id}/deactivate/`, `/reactivate/` | Admin | Sets `is_active`; returns the user. Idempotent: repeating it changes nothing and isn't audited again. |
| `POST /api/v1/users/{id}/send-password-reset/` | Admin | Emails a reset link, or a fresh invite if the user never set a password. `204`; `400` for an inactive user. |
| `PATCH /api/v1/users/{id}/role/` | Admin | `{"role"}`. Grant/revoke a role; also sets Django admin access (below). |
| `POST /api/v1/password-reset/` | Anonymous | `{"email"}` → always `204`, so it can't reveal which addresses have accounts. Throttled to 5 an hour per email. Inactive users get no mail. |
| `POST /api/v1/password-reset/confirm/` | Anonymous | `{"uid", "token", "new_password"}` → `204`. Completes both resets and invites. `400` for a used, expired (Django's `PASSWORD_RESET_TIMEOUT`, 3 days) or tampered link. |
| `GET /api/v1/audit-log/?module=&actor=` | Admin | Cross-module audit trail, filterable by module and actor. |

There is no `PUT` on users (`405`). `DELETE /users/{id}/` (admin) deletes an account for good, with its download records and access requests, e.g. when a visitor asks to be erased: `204`; `400` for the admin's own account; `409` for an account that created content, which keeps its author (`WorkflowMixin.created_by` is `PROTECT`), so deactivate those instead. Audit rows the user made stay, without the link to them, and the deletion is audited as `user_delete` with the username, email and role.

## Rules

- **Django admin access follows the role.** `User.save()` sets `is_staff` and `is_superuser` to `role == "admin"` on every save, whichever path changed the role (this API, the admin site, `seed_demo`). `createsuperuser` makes an `admin`. Migration `accounts.0003` promoted existing superusers to `admin` and aligned everyone else.
- **Admins can't lock themselves out.** An admin can't demote or deactivate themselves, and the last active admin can't be demoted or deactivated (`400`). One guard, `guard_admin_lockout` in `apps/accounts/services.py`, serves both endpoints.
- **Deactivation takes effect immediately.** SimpleJWT's `CHECK_USER_IS_ACTIVE` (on by default) rejects an inactive user's existing access tokens (`401`) and their refresh tokens at `/token/refresh/` (`401`), and login fails too.
- **Emails are unique** (case-insensitive) across accounts, because resets are requested by email.
- **Passwords** go through `AUTH_PASSWORD_VALIDATORS`. Errors come back under the field: `password` on create, `new_password` elsewhere.
- **Links:** invites and resets both point to `{FRONTEND_URL}/reset-password?uid=...&token=...`. A token is derived from the current password hash, so it works once.

## Audit log

Every admin write adds one `AuditLog` row with `module="accounts"` and `target="user:<id>"`. Passwords never appear.

| `action` | `metadata` |
|---|---|
| `user_create` | `{"role", "invite": bool}` |
| `user_update` | `{"changes": {"field": [old, new]}}`, only fields that actually changed |
| `user_deactivate`, `user_reactivate` | `{}` |
| `password_reset_sent` | `{}` |
| `role_change` | `{"old_role", "new_role"}` |

## Request/response shapes

**User** (`GET /users/`, `/users/{id}/`, `/users/me/`, and the create/update/deactivate responses):
```json
{"id": 7, "username": "rafi", "email": "rafi@example.org", "first_name": "Rafi", "last_name": "K",
 "role": "researcher", "is_active": true, "must_change_password": false,
 "date_joined": "2026-09-28T10:00:00Z", "last_login": null}
```
Serializer: `UserSerializer` (`apps/accounts/serializers.py`). Create takes the writable fields plus `username`, `role` and an optional `password` (`UserCreateSerializer`).

**`GET /users/me/role/`**
```json
{"id": 1, "email": "user@example.com", "role": "editor"}
```

**`GET /audit-log/`**
```json
[{"id": 1, "actor": 1, "module": "content", "action": "status_transition", "target": "contentblock:4", "metadata": {"previous_status": "draft", "new_status": "in_review"}, "timestamp": "2026-09-21T10:00:00Z"}]
```
Serializer: `AuditLogSerializer`. Currently unpaginated (see [README.md](README.md#pagination)).

## Email

Configured by env only (`EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`, `FRONTEND_URL`; see `.env.example`). Dev prints mail to the console. Staging sends through Gmail SMTP, production through Amazon SES (issue #7). If sending an invite fails, the account isn't created, so the admin can retry.

## Explicitly excluded from this v1 contract

- Self-registration: no PRD asks for it here (Module F's territory for donors).
- Per-user or per-object permissions: PRD H "Out of Scope".
- Hard delete or anonymisation: only if a data-removal request ever arrives.
- `accounts_apikey` and `accounts_notificationlog`: `docs/erd/README.md:121,123` label both "recommended addition, no PRD names them".

## Role enum (reference)

`apps/accounts/models.py` — `Role` TextChoices: `public` (Donor/Visitor), `researcher`, `editor`, `fellow` (Intern/Fellow), `admin`. Deliberately matches the companion Next.js frontend's mock-auth `Role` type values (per backend CLAUDE.md's Architectural Decisions), including using `public` rather than `donor` for that reason.
