# Branch Protection Setup — apply to both `pri-frontend` and `pri-backend`

> **Automated:** `scripts/setup-github-protection.sh` applies sections 2-4 and 6 (rulesets and Environments) and prints the
> secrets still to add by hand. It is safe to re-run.
>
> **Plan limit:** rulesets and environment reviewers on a private repo need GitHub Pro/Team (or a public repo). On Free the
> script reports a 403 for those steps. Until the plan changes, the workflow in CONTRIBUTING.md is followed by convention:
> CI and `pr-guard` still run on every PR but do not block merging, so merge only when they are green.

Run through this once per repo, right after creation, before the first commit lands.

## 1. Create branches

```bash
git checkout -b dev
git push -u origin dev
git checkout -b staging
git push -u origin staging
# main already exists as default
```

Set `dev` as the repo's default branch (Settings → General → Default branch)
so new PRs target it automatically.

## 2. Protect `main`

Settings → Branches → Add rule → branch name pattern `main`:
- [ ] Require a pull request before merging
- [ ] Require status checks to pass before merging (select CI test job once it exists)
- [ ] Require branches to be up to date before merging
- [ ] Do not allow bypassing the above settings (include yourself)
- [ ] Block force pushes
- [ ] Block deletions

## 3. Protect `staging`

Same rule pattern as `main`, target `staging`.

## 4. Protect `dev`

- [ ] Require a pull request before merging
- [ ] Require status checks to pass (lint/tests)
- [ ] Block force pushes
- [ ] Block deletions
- [ ] (Leave "require approvals" at 0 for now — solo dev. Set to 1 when the team grows.)

## 5. Secrets (per environment)

Settings → Secrets and variables → Actions → add per-environment secrets
(use GitHub Environments, not repo-level secrets, so staging/prod stay isolated):

- [ ] `DATABASE_URL` (staging)
- [ ] `DATABASE_URL` (production)
- [ ] `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (staging bucket)
- [ ] `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (production bucket)
- [ ] Django `SECRET_KEY` **[Backend]**
- [ ] Any Next.js public/runtime env vars **[Frontend]**

## 6. GitHub Environments

Settings → Environments → create `staging` and `production`:
- [ ] `production` environment: require a reviewer before deploy runs (even if reviewer = you, this adds a manual gate)
- [ ] Attach the matching secrets from step 5 to each environment

## 7. Repo hygiene

- [ ] Add `CONTRIBUTING.md` (workflow doc) to repo root
- [ ] Add `.github/PULL_REQUEST_TEMPLATE.md`
- [ ] Add `.env.example` listing required env vars with dummy values
- [ ] Add `.gitignore` covering `.env`, `node_modules`/`venv`, migration cache, `__pycache__`
- [ ] Confirm three S3 buckets exist and are named consistently: `pri-dev`, `pri-staging`, `pri-prod` **[Backend]**

## 8. When the team grows to 3–5

- [ ] Add `CODEOWNERS` mapping modules to owners
- [ ] Raise `dev` required approvals from 0 to 1
- [ ] Raise `main`/`staging` required approvals to 1 (or 2 for `main`)
