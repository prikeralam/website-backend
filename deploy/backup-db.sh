#!/usr/bin/env bash
# Dumps the environment's Postgres container to its bucket: s3://<bucket>/backups/<env>/<time>-<label>.dump
# (custom format; restore with pg_restore). Uploaded next to remote-deploy.sh, which runs it before every
# migration ("predeploy") and installs a nightly cron job ("nightly"). The bucket expires backups/ after
# 30 days (deploy/aws/host.yml). The upload uses the host's instance role, so no AWS keys are needed.
set -euo pipefail

cd /opt/pri-backend
label=${1:-manual}
[[ $label =~ ^[a-z]+$ ]] || { echo "bad label" >&2; exit 1; }
env_value() { grep -E "^$1=" .env | tail -n1 | cut -d= -f2-; }

# Read the list first: `docker compose ... | grep -q` under pipefail can fail when grep exits early.
services=$(docker compose config --services)
if ! grep -qx db <<< "$services"; then
  echo "No db service here; nothing to back up."
  exit 0
fi

bucket=$(env_value AWS_STORAGE_BUCKET_NAME)
region=$(env_value AWS_S3_REGION_NAME)
environment=$(env_value ENVIRONMENT)
user=$(env_value POSTGRES_USER)
database=$(env_value POSTGRES_DB)
[ -n "$bucket" ] && [ -n "$environment" ] && [ -n "$user" ] && [ -n "$database" ] || { echo "backup settings missing from .env" >&2; exit 1; }

stamp=$(date -u +%Y%m%dT%H%M%SZ)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
file="$stamp-$label.dump"

docker compose exec -T db pg_dump -U "$user" -d "$database" -Fc > "$work/$file"
[ -s "$work/$file" ] || { echo "empty dump" >&2; exit 1; }
docker run --rm -v "$work:/backup:ro" amazon/aws-cli s3 cp "/backup/$file" "s3://$bucket/backups/$environment/$file" \
  --region "${region:-ap-south-1}" --only-show-errors
echo "Backed up to s3://$bucket/backups/$environment/$file ($(du -h "$work/$file" | cut -f1))"
