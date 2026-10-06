# pri-backend

Django + DRF backend for PRI (Policy and Research Initiative) — CMS content, projects, publications, the data repository and user/role management.

See `CLAUDE.md` for the stack and architecture, and `docs/api/` for the API contract. Local setup is in `CLAUDE.md` under "Running locally".

## Deploying

Deploys are automatic, driven by GitHub Actions on merge:

| Merge into | Result |
|---|---|
| `dev` | lint, tests, Docker build only (no deploy) |
| `staging` | tests, image pushed to GHCR, deployed to the staging EC2 host |
| `main` | tests, image promoted from staging (or built), database backed up, deployed to the production host, release tagged |

Flow: `feat/*` -> `dev` -> `staging` -> `main`. Health check: `GET /healthz/`. The branch flow, workflows, secrets and release steps are described in [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md) (section 5).

Setup scripts: `scripts/setup-github-protection.sh` (GitHub Environments and branch rulesets). Production and staging config lives in `deploy/`.
