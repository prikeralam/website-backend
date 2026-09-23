## Summary

<!-- What does this change do, and why. -->

Closes #

## Type

- [ ] feat
- [ ] fix
- [ ] chore
- [ ] refactor
- [ ] docs

## Checklist

- [ ] Targets `dev` (not `main`/`staging`, unless this is a release/hotfix PR)
- [ ] Migrations included, if any models changed **[Backend]**
- [ ] Ran `migrate --plan` against staging config **[Backend]**
- [ ] Env vars documented in `.env.example` if new ones were added
- [ ] Bucket/DB names correct for the target environment (no hardcoded prod values)
- [ ] Tested locally against dev config
- [ ] Self-reviewed the diff (not just skimmed)
- [ ] No secrets, credentials, or `.env` files committed

## Notes for reviewer

<!-- Anything that needs a second look, e.g. irreversible migration steps. -->
