# Contributing / Git Workflow — PRI Website

Applies to both `pri-frontend` (Next.js) and `pri-backend` (Django/DRF).
Backend-only steps are marked **[Backend]**. Everything else applies to both repos.

---

## 1. Branches

Three long-lived branches. Nothing else is long-lived.

| Branch | Purpose | Protected |
|---|---|---|
| `main` | Production. Deployed automatically on merge. | Yes |
| `staging` | Pre-prod. Mirrors prod config, sample/sanitized data. | Yes |
| `dev` | Integration branch. Default branch for local work. | Yes (solo reviewer allowed) |

Short-lived work branches, cut from `dev`, deleted after merge:

```
feat/<issue#>-<short-description>
fix/<issue#>-<short-description>
chore/<short-description>
refactor/<short-description>
docs/<short-description>
```

Examples:
```
feat/42-cms-content-model
fix/58-s3-presigned-url-expiry
chore/bump-drf-version
```

### Promotion flow

```
feat/xyz  → PR → dev
dev       → PR → staging   (batch features, deploy, smoke test)
staging   → PR → main      (release, tag)
```

Hotfixes to prod: branch `fix/*` from `main` directly, PR into `main`,
then immediately open a backport PR of the same fix into `staging` and `dev`
so it isn't lost on the next promotion.

---

## 2. Commit messages — Conventional Commits

```
<type>(<scope>): <short summary>
```

**Types:** `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`, `ci`

**Scope:** the PRD module/section name — `cms`, `data-repo`, `s3`, `auth`, `homepage`, `about`

Examples:
```
feat(cms): add draft-review-approve-publish state machine
fix(s3): correct presigned URL expiry to 15 min
chore(deps): bump djangorestframework to 3.15
docs(prd): add module C open decisions
```

---

## 3. Issues

- One GitHub Issue per PRD section/module (Phase 1: Homepage, About PRI,
  Module A, Data Repository & Library, Module C). Split into sub-issues
  only if a module genuinely spans multiple weeks.
- Branch name includes the issue number.
- PR description ends with `Closes #<issue>` to auto-close on merge.
- Trivial one-line fixes don't need an issue — just a `fix/` branch and a direct PR.

---

## 4. Pull requests

- Every PR targets `dev` (or `main`/`staging` only for the promotion/hotfix
  flows above) — never push directly to a protected branch.
- Self-review before merging, even solo: open the PR, step away, come back
  and read the diff as if it were someone else's code. This is the actual
  QA step when there's no second reviewer.
- Use the PR checklist in `.github/PULL_REQUEST_TEMPLATE.md`.
- Treat any PR containing Claude Code output with the same scrutiny as a
  junior dev's PR — check for silently assumed env vars, wrong env's
  bucket/DB names, and untested migrations.

---

## 5. Environments

| Env | Branch | Postgres | S3 bucket |
|---|---|---|---|
| Dev | local / `dev` | local or shared dev instance, seeded/fake data | `pri-dev` |
| Staging | `staging` | separate instance, prod-like schema, sanitized data | `pri-staging` |
| Production | `main` | prod instance, real data, automated backups | `pri-prod` |

Never point staging at the prod database or prod bucket. A staging bug
that deletes rows or overwrites files becomes a prod incident.

CI/CD (GitHub Actions):
- PR / push to `dev` → lint + tests only.
- Merge to `staging` → tests, then deploy to staging.
- Merge to `main` → tests, then deploy to prod, tag a release.

---

## 6. Versioning

Tag `main` on every prod deploy: `v0.1.0`, `v0.2.0`, …
Frontend and backend repos version independently — don't try to keep
tag numbers in sync across the two repos.

---

## 7. Migrations **[Backend]**

- Migration files ship in the *same* PR as the model change that produced them.
- Run `python manage.py migrate --plan` against staging before running
  against prod.
- Backup prod Postgres before any migration touching existing tables
  (not just additive ones) — automate as a pre-deploy CI step.
- Irreversible migrations (column drops, type changes) are two PRs:
  1. Additive/compatible change, deploy, backfill.
  2. Drop the old column, only after confirming nothing references it.

---

## 8. What this deliberately skips

No `release/*` or full GitFlow branch taxonomy — three long-lived branches
plus short-lived work branches is the right complexity for a solo developer
now and for a 3–5 person team later. Add `CODEOWNERS` and require a second
approver when the team grows; the branch/environment structure doesn't change.
