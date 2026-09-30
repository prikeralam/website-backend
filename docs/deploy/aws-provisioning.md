# AWS provisioning

The AWS side of the deploy pipeline (`.github/CONTRIBUTING.md` section 5) lives in PRI's own account,
`305846488655`, region `ap-south-1` (Mumbai). Each environment is **one EC2 host shared by the backend and the
frontend**, described by `deploy/aws/host.yml`. Staging exists; production is not provisioned yet.

Until 2026-09-30, staging ran as two hosts (one per repo) in the owner's personal account `949820257880`; see
"Retiring the old account" below.

| Stack | Region | Template | What it holds |
|---|---|---|---|
| `pri-staging` | ap-south-1 | `deploy/aws/host.yml` (`Environment=staging`) | EC2 host, static IP `15.252.128.131`, security group, deploy key pair, instance role, `pri-staging-305846488655` bucket |
| `pri-account-budget` | us-east-1 | `deploy/aws/account-budget.yml` | `pri-monthly` budget: $40/month gross spend (credits excluded, so it warns while the free-plan credit is still paying), emails contact@priresearch.in at 50/80/100% actual and 100% forecast |

## The shared host

- **Machine:** `t3.small` (2 GB; one host runs both apps and staging's Postgres), Ubuntu 24.04 amd64 (the images are
  amd64-only), 20 GB gp3, 2 GB swap, standard CPU credits (no surplus billing).
- **Layout:** each repo's deploy workflow uploads to its own directory and runs its own compose project:
  - `/opt/pri-backend`: `deploy/docker-compose.staging.yml` (app on `127.0.0.1:8000`, Postgres container);
  - `/opt/pri-frontend`: the frontend's `deploy/docker-compose.yml` (Next.js on `127.0.0.1:3000`).
- **Nginx and TLS run on the host** (Ubuntu's nginx and certbot packages), not in containers. Each deploy calls
  `sudo pri-nginx-site <name> <SERVER_NAME> <dir>`, a script the template installs, which:
  1. asks Let's Encrypt for a certificate (webroot mode) if there isn't one yet and the name already resolves to this
     host;
  2. renders the repo's `nginx.conf.template` (HTTPS) when a certificate exists, or `nginx.http.conf.template`
     (plain HTTP) when it doesn't, into `/etc/nginx/conf.d/<name>.conf`, then tests and reloads nginx.

  So a fresh host serves the apps over HTTP until DNS points at it, and the next deploy after the DNS change (or
  running the script by hand) switches it to HTTPS. Renewals run from certbot's systemd timer through the same
  webroot and reload nginx; nothing stops.
- **Media:** the bucket is private and encrypted. The app reaches it through the instance role (IMDSv2, hop limit 2 so
  containers can reach it), so `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` stay empty in the env file. File URLs are
  presigned. The frontend's `IMAGE_HOSTS` variable must list the bucket's hostnames.
- **Access:** SSH as `ubuntu` with the deploy key, open to 0.0.0.0/0 because GitHub-hosted runners have no fixed IPs
  (key-only). Session Manager also works through the instance role if the key is lost.
- **Bootstrap log:** `/var/log/pri-bootstrap.log` on the host.

The AMI is a pinned parameter: resolving it from SSM on each update would replace the instance, and with it the
Postgres volume and the certificates.

### Creating or updating a host

Run in Git Bash with `MSYS_NO_PATHCONV=1`, or the `/aws/...` parameter path gets rewritten. The CLI profile `pri`
signs in as the IAM user `pri-admin` (`aws login --profile pri`).

```bash
aws ssm get-parameter --profile pri \
  --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id \
  --query Parameter.Value --output text
aws cloudformation deploy --profile pri --stack-name pri-staging \
  --template-file deploy/aws/host.yml --capabilities CAPABILITY_NAMED_IAM \
  --tags Project=pri Environment=staging \
  --parameter-overrides Environment=staging ImageId=<ami> InstanceType=t3.small \
  "SshPublicKey=$(cat ~/.ssh/pri-staging-host-deploy.pub)"
```

A new host has a new IP: update `EC2_HOST` in **both** repos' `staging` Environment, re-pin `EC2_SSH_KNOWN_HOSTS`
(check `ssh-keyscan -t ed25519 <ip>` against the `SSH HOST KEY FINGERPRINTS` block in
`aws ec2 get-console-output`; on Windows set `PYTHONUTF8=1`), and move the A records.

### GitHub `staging` Environment (both repos)

| Secret | Value |
|---|---|
| `EC2_HOST` | `15.252.128.131` |
| `EC2_USER` | `ubuntu` |
| `EC2_SSH_KEY` | private deploy key, kept locally at `~/.ssh/pri-staging-host-deploy` (the same key in both repos) |
| `EC2_SSH_KNOWN_HOSTS` | the verified host key line, kept at `~/.ssh/pri-staging-host.known_hosts` |
| `APP_ENV_FILE` | this repo: the full runtime env: `ENVIRONMENT=staging`, `DEBUG=False`, `api-staging.priresearch.in` in `SERVER_NAME`/`ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`, `DATABASE_URL` at host `db` with the matching `POSTGRES_*`, `AWS_STORAGE_BUCKET_NAME=pri-staging-305846488655`, `AWS_S3_REGION_NAME=ap-south-1`, `FRONTEND_URL=https://staging.priresearch.in`. Kept at `~/.pri-deploy/backend-staging.env`; GitHub secrets can't be read back, so edit that copy. |

DNS (GoDaddy): `staging.priresearch.in` and `api-staging.priresearch.in` are A records to the host's static IP.

## Production (not provisioned)

Same template with `Environment=production` and stack `pri-production`: one host for `priresearch.in`,
`www.priresearch.in` and `api.priresearch.in`, its own bucket and deploy key. `deploy-production.yml` still expects an
RDS instance to snapshot before deploying; that changes with the production work (the database is planned as a
container on the host, backed up to S3).

## Retiring the old account

Staging's data (Postgres dump and the media bucket) was copied from the old hosts in account `949820257880`
(`pri-staging` backend host, `pri-frontend-staging` frontend host, bucket `pri-staging-949820257880`). Once the new
host is verified, delete both stacks there, then empty and delete the retained bucket and the `pri-account-budget`
stack.
