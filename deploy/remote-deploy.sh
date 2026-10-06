#!/usr/bin/env bash
# Runs on the EC2 host, uploaded by the deploy-staging / deploy-prod workflows.
# Swaps in the new .env (which pins IMAGE), migrates, restarts, smoke-tests, and puts the
# previous .env (and therefore image) back if anything fails.
#
# Migrations are forward-only: a rollback restores the old image but does not undo them,
# which is why CONTRIBUTING.md requires backward-compatible (expand/contract) migrations.
set -euo pipefail

cd /opt/pri-backend
[ -f .env.new ] || { echo ".env.new missing" >&2; exit 1; }

env_value() { grep -E "^$1=" .env | tail -n1 | cut -d= -f2-; }

if [ -f .env ]; then cp .env .env.previous; fi
mv .env.new .env

server_name=$(env_value SERVER_NAME)
[ -n "$server_name" ] || { echo "SERVER_NAME missing from the env file" >&2; exit 1; }

rollback() {
  echo "Deploy failed." >&2
  if [ -f .env.previous ]; then
    echo "Restoring $(grep -E '^IMAGE=' .env.previous | tail -n1)" >&2
    cp .env.previous .env
    docker compose up -d --remove-orphans || true
  else
    echo "No previous deploy to restore." >&2
  fi
  exit 1
}

docker compose pull web || rollback

# Read the list first: `docker compose ... | grep -q` under pipefail can fail when grep exits early.
services=$(docker compose config --services) || rollback
if grep -qx db <<< "$services"; then
  docker compose up -d --wait db || rollback
  # Restore point before any migration runs (CONTRIBUTING.md section 7).
  bash /opt/pri-backend/backup-db.sh predeploy || rollback
  # Nightly at 02:47 IST; replaces any earlier entry for this job.
  { crontab -l 2>/dev/null | grep -v "pri-backup-db" || true
    echo "17 21 * * * /bin/bash /opt/pri-backend/backup-db.sh nightly >> /opt/pri-backend/backup.log 2>&1 # pri-backup-db"
  } | crontab -
fi

docker compose run --rm --no-deps web python manage.py migrate --plan || rollback
docker compose run --rm --no-deps web python manage.py migrate --noinput || rollback
docker compose up -d --remove-orphans || rollback

# The host's nginx routes this app's name to it (HTTPS once a certificate exists; see deploy/aws/host.yml).
sudo /usr/local/sbin/pri-nginx-site pri-backend "$server_name" /opt/pri-backend || rollback

healthy=0
for _ in $(seq 1 30); do
  if curl -fsS -H "Host: $server_name" http://localhost/healthz/ >/dev/null; then
    healthy=1
    break
  fi
  sleep 2
done
[ "$healthy" = 1 ] || { docker compose logs --tail=50 web >&2; rollback; }

echo "Healthy: $(env_value IMAGE)"
docker image prune -f >/dev/null
