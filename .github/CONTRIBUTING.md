# Contributing / Git Workflow — PRI Website

Applies to both `pri-frontend` (Next.js) and `pri-backend` (Django/DRF).
Backend-only steps are marked **[Backend]**. Everything else applies to both repos.

---

## 1. Branches

Three long-lived branches. Nothing else is long-lived.

| Branch | Purpose | Protected |
|---|---|---|
| `main` | Production. Deployed on merge, after a manual approval. | Yes |
| `staging` | Pre-prod. Mirrors prod config, sample/sanitized data. Deployed on merge. | Yes |
| `dev` | Integration branch. Default branch for local work. | Yes (solo reviewer allowed) |

"Protected" is the intent; see [Enforcement](#enforcement) for what GitHub actually blocks today.

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

Hotfixes to prod: branch `fix/*` from `main` directly, PR into `main`.
The Hotfix backport workflow then opens `backport/<pr>-to-staging` and
`backport/<pr>-to-dev` PRs for you, so the fix isn't lost on the next promotion.
Merge both. If a cherry-pick conflicts, the workflow opens an issue instead and
you cherry-pick by hand.

Merge methods: work branch into `dev` is a squash merge. Promotion PRs
(`dev` -> `staging`, `staging` -> `main`) are **merge commits**. Squashing a
promotion makes the branches diverge and every later promotion conflicts.

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

## 5. Environments and CI/CD

| Env | Branch | Postgres | S3 bucket |
|---|---|---|---|
| Dev | local / `dev` | local Docker Compose (`docker-compose.yml`), seeded/fake data | `pri-dev` |
| Staging | `staging` | Postgres container on the staging EC2 host, prod-like schema, sanitized data | `pri-staging` |
| Production | `main` | RDS instance, real data, snapshot before every deploy | `pri-prod` |

Never point staging at the prod database or prod bucket. A staging bug
that deletes rows or overwrites files becomes a prod incident. The deploy
action enforces part of this: `APP_ENV_FILE` must declare the same
`ENVIRONMENT=` as the environment being deployed, and the app refuses to
start deployed with `DEBUG=True` or without a bucket.

### Workflows (`.github/workflows/`)

| Workflow | Runs on | What it does |
|---|---|---|
| `ci.yml` | every PR, push to `dev`, and called by both deploy workflows | `lint` (ruff), `test` (`manage.py check`, `makemigrations --check`, `migrate`, `test` on Postgres 16), `docker-build` (builds the image, boots it against Postgres with a real-looking `ALLOWED_HOSTS`, requests `/healthz/`, and waits for Docker to report it healthy) |
| `pr-guard.yml` | PRs into `dev`, `staging`, `main` | `branch-flow` fails a PR whose source/target pair is not an allowed promotion path (section 1) |
| `deploy-staging.yml` | push to `staging` | CI, then builds and pushes the image to GHCR, then deploys it to the staging EC2 host over SSH (`staging` Environment) |
| `deploy-production.yml` | push to `main` | CI, then image, then manual approval, then RDS snapshot, then SSH deploy, then git tag and GitHub Release (`production` Environment) |
| `hotfix-backport.yml` | push to `main` from a `fix/*` PR | opens backport PRs into `staging` and `dev` |

Images are tagged `sha-<commit>` and `tree-<git tree hash>`. A merge of
`staging` into `main` has the same tree as staging, so production
**promotes the image already tested on staging** (retag, no rebuild). A hotfix
or any tree never seen on staging is built fresh.

### Release flow

1. Merge work branches into `dev` (squash) once CI is green.
2. Open `dev` -> `staging`, merge commit. The staging deploy runs; smoke test it.
3. Open `staging` -> `main`, merge commit. The production run pauses at the
   `production` Environment for approval. Approve it: the RDS snapshot is
   taken, the image is deployed, and the release is tagged (section 6).
4. Hotfix: `fix/*` from `main` -> `main`, then merge the two backport PRs.

### Secrets and variables

Set per GitHub Environment, not at repo level, so staging and prod stay isolated
(`gh secret set NAME --env staging`):

| Where | Name | Kind |
|---|---|---|
| `staging` and `production` | `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`, `EC2_SSH_KNOWN_HOSTS`, `APP_ENV_FILE` | secrets |
| `production` only | `AWS_ROLE_ARN` | secret |
| `production` only | `AWS_REGION`, `RDS_INSTANCE_ID` | variables |
| repository (optional) | `BACKPORT_TOKEN` | secret; without it backport PRs don't trigger CI, close and reopen each one |

`APP_ENV_FILE` is the full runtime `.env` (see `.env.example`). Setting up the
GitHub side is scripted in `scripts/setup-github-protection.sh`; provisioning
the AWS side is tracked in issue #7.

### Enforcement

The rulesets that would block merging on red checks, direct pushes, force-pushes
and the wrong merge method need GitHub Pro/Team on a private repo, so they are
**not applied yet** (issue #6). Until they are, the flow is followed by
convention, and CI and `pr-guard` run but do not block:

- Merge only when `lint`, `test`, `docker-build` and `branch-flow` are green.
- Never push directly to `dev`, `staging` or `main`; a push to `main` deploys to production.
- Never force-push or delete the long-lived branches.
- Use the merge methods in section 1.

Once the plan allows it, run `scripts/setup-github-protection.sh`; it is safe to re-run.

---

## 6. Versioning

Every successful prod deploy is tagged and published as a GitHub Release
automatically (`v0.1.0` for the first). While pre-1.0, a `feat` commit since the
last tag bumps the minor version and anything else bumps the patch.
Frontend and backend repos version independently — don't try to keep
tag numbers in sync across the two repos.

---

## 7. Migrations **[Backend]**

- Migration files ship in the *same* PR as the model change that produced them.
- Run `python manage.py migrate --plan` against staging before running
  against prod.
- Prod Postgres is snapshotted automatically before every production deploy
  (RDS snapshot in `deploy-production.yml`), so any release that migrates has a restore point.
- Irreversible migrations (column drops, type changes) are two PRs:
  1. Additive/compatible change, deploy, backfill.
  2. Drop the old column, only after confirming nothing references it.

---

## 8. What this deliberately skips

No `release/*` or full GitFlow branch taxonomy — three long-lived branches
plus short-lived work branches is the right complexity for a solo developer
now and for a 3–5 person team later. Add `CODEOWNERS` and require a second
approver when the team grows; the branch/environment structure doesn't change.
