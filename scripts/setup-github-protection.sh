#!/usr/bin/env bash
# Applies the repo hygiene from the branch-protection checklist (.github/BRANCH-PROTECTION-CHECKLIST.md):
#   1. repo settings (auto-delete merged branches)
#   2. GitHub Environments `staging` and `production` (production needs a reviewer; deploys only from
#      the matching branch)
#   3. rulesets protecting dev, staging and main
# Safe to re-run: existing environments and rulesets are updated in place.
#
# Needs: gh logged in as a repo admin. Rulesets and environment reviewers need GitHub Pro/Team on a
# private repo; on Free those steps report a 403 and the script exits non-zero after trying the rest.
#
# Usage: scripts/setup-github-protection.sh [owner/repo]
set -uo pipefail

repo="${1:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}"
user_id="$(gh api user --jq .id)"
failed=0

step() { printf '\n== %s\n' "$1"; }
warn() { printf 'FAILED: %s\n' "$1" >&2; failed=1; }

# Required status checks: the job names from ci.yml and pr-guard.yml.
checks='[{"context":"lint"},{"context":"test"},{"context":"docker-build"},{"context":"branch-flow"}]'

step "Repo settings"
gh api -X PATCH "repos/$repo" -F delete_branch_on_merge=true --silent \
  && echo "Merged branches are deleted automatically." \
  || warn "could not update repo settings"

step "Environments"
gh api -X PUT "repos/$repo/environments/staging" --input - --silent <<JSON \
  && echo "staging: ok" || warn "could not create the staging environment"
{"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}
JSON
gh api -X POST "repos/$repo/environments/staging/deployment-branch-policies" -f name=staging --silent 2>/dev/null || true

gh api -X PUT "repos/$repo/environments/production" --input - --silent <<JSON \
  && echo "production: ok (required reviewer: user $user_id)" || warn "could not create the production environment with a required reviewer"
{"reviewers":[{"type":"User","id":$user_id}],"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}
JSON
gh api -X POST "repos/$repo/environments/production/deployment-branch-policies" -f name=main --silent 2>/dev/null || true

# Promotion PRs (dev->staging, staging->main) must be merge commits: squashing them makes the branches
# diverge and every later promotion conflicts. Work-branch PRs into dev are squashed. Because promotion
# merges leave merge commits the source branch lacks, "require branch to be up to date" is off for
# staging/main (it would force merging staging back into dev, which pr-guard forbids).
ruleset() { # name, branch, merge method
  local name="$1" branch="$2" method="$3" id
  local body
  body=$(cat <<JSON
{
  "name": "$name",
  "target": "branch",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": ["refs/heads/$branch"], "exclude": []}},
  "bypass_actors": [],
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "pull_request", "parameters": {
      "required_approving_review_count": 0,
      "dismiss_stale_reviews_on_push": false,
      "require_code_owner_review": false,
      "require_last_push_approval": false,
      "required_review_thread_resolution": false,
      "allowed_merge_methods": ["$method"]
    }},
    {"type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": false,
      "required_status_checks": $checks
    }}
  ]
}
JSON
)
  id=$(gh api "repos/$repo/rulesets" --jq ".[] | select(.name == \"$name\") | .id" 2>/dev/null | head -n1)
  if [ -n "$id" ]; then
    printf '%s' "$body" | gh api -X PUT "repos/$repo/rulesets/$id" --input - --silent \
      && echo "$name: updated" || warn "could not update ruleset $name"
  else
    printf '%s' "$body" | gh api -X POST "repos/$repo/rulesets" --input - --silent \
      && echo "$name: created" || warn "could not create ruleset $name (private repos need GitHub Pro/Team)"
  fi
}

step "Branch rulesets"
ruleset "protect-dev" dev squash
ruleset "protect-staging" staging merge
ruleset "protect-main" main merge

step "Secrets still to add by hand (values are never handled by this script)"
cat <<'TXT'
  environment "staging":    EC2_HOST EC2_USER EC2_SSH_KEY EC2_SSH_KNOWN_HOSTS APP_ENV_FILE
  environment "production": EC2_HOST EC2_USER EC2_SSH_KEY EC2_SSH_KNOWN_HOSTS APP_ENV_FILE AWS_ROLE_ARN
                            + variables AWS_REGION RDS_INSTANCE_ID
  repository (optional):    BACKPORT_TOKEN
  Details and how to produce each value: docs/deploy/aws-provisioning.md
  Set one with: gh secret set NAME --env staging   (or --env production)
TXT

if [ "$failed" -ne 0 ]; then
  printf '\nSome steps failed (see FAILED lines above).\n' >&2
  exit 1
fi
printf '\nAll steps applied.\n'
