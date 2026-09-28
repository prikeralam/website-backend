# AWS provisioning

The AWS side of the deploy pipeline (`.github/CONTRIBUTING.md` section 5) is two
CloudFormation stacks in account `949820257880`. Staging exists; production is not
provisioned yet.

| Stack | Region | Template | What it holds |
|---|---|---|---|
| `pri-account-budget` | us-east-1 | `deploy/aws/account-budget.yml` | `pri-monthly` cost budget: $20/month gross (credits excluded, so alerts fire while credits are still paying), email at 50/80/100% actual and 100% forecast |
| `pri-staging` | ap-south-1 | `deploy/aws/staging.yml` | EC2 host, static IP, security group, deploy key pair, instance role, `pri-staging-<account id>` bucket |

## Staging

- **Host:** `t3.micro`, Ubuntu 24.04 amd64 (the CI image is amd64-only, so no Graviton), 20 GB gp3, 2 GB swap, standard CPU credits (no surplus billing). Runs `deploy/docker-compose.staging.yml`: app, Postgres container, nginx.
- **Hostname:** `<ip-with-dashes>.sslip.io` (a wildcard DNS name that resolves to the IP it spells), currently `15-206-144-63.sslip.io`. Swapping in a real subdomain later means an A record, a new certbot certificate, and `SERVER_NAME`/`ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` in `APP_ENV_FILE`.
- **TLS:** certbot on the host, first issued at boot. Renewals use the standalone server: the renewal hooks stop the nginx container for a few seconds to free port 80.
- **Media:** the bucket is private and encrypted. The app reaches it through the instance role (IMDSv2, hop limit 2 so containers can reach it), so `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` stay empty in the env file. File URLs are presigned.
- **Access:** SSH as `ubuntu` with the deploy key, open to 0.0.0.0/0 because GitHub-hosted runners have no fixed IPs (key-only, no passwords). Session Manager also works through the instance role if the key is lost.
- **Bootstrap log:** `/var/log/pri-bootstrap.log` on the host.

The AMI is a pinned parameter. Resolving it from SSM on each update would replace
the instance, and the Postgres volume with it.

### Recreating or updating it

Run in Git Bash with `MSYS_NO_PATHCONV=1`, or the `/aws/...` parameter path gets rewritten.

```bash
aws ssm get-parameter --region ap-south-1 \
  --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id \
  --query Parameter.Value --output text
aws cloudformation deploy --region ap-south-1 --stack-name pri-staging \
  --template-file deploy/aws/staging.yml --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides ImageId=<ami> "SshPublicKey=$(cat ~/.ssh/pri-staging-deploy.pub)"
```

A new stack gets a new IP, and so a new hostname: update `APP_ENV_FILE` and
`EC2_HOST`, and re-pin `EC2_SSH_KNOWN_HOSTS`. Check the scanned key against the
`SSH HOST KEY FINGERPRINTS` block in `aws ec2 get-console-output` before trusting it.

### GitHub `staging` Environment

| Secret | Value |
|---|---|
| `EC2_HOST` | the static IP |
| `EC2_USER` | `ubuntu` |
| `EC2_SSH_KEY` | private deploy key (kept locally at `~/.ssh/pri-staging-deploy`) |
| `EC2_SSH_KNOWN_HOSTS` | the verified `ssh-keyscan -t ed25519 <ip>` line |
| `APP_ENV_FILE` | the full runtime env: `ENVIRONMENT=staging`, `DEBUG=False`, the hostname in `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`/`SERVER_NAME`, `DATABASE_URL` at host `db`, the matching `POSTGRES_*`, the bucket name and `AWS_S3_REGION_NAME=ap-south-1` |

GitHub secrets can't be read back, so the local copy of `APP_ENV_FILE` (kept outside
the repo) is the one to edit when a value changes.

## Production (not provisioned)

Planned per CONTRIBUTING.md: its own EC2 host, RDS Postgres (snapshotted by
`deploy-production.yml`, which needs `AWS_ROLE_ARN` for GitHub OIDC plus the
`AWS_REGION` and `RDS_INSTANCE_ID` variables), and a `pri-prod-<account id>` bucket.
`deploy/docker-compose.prod.yml` already expects this.
