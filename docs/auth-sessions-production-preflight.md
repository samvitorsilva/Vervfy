# Production auth-session repair: phone-friendly preflight

**Status:** The SQL Editor checks alone do not apply migration 0032. Do not run arbitrary SQL to create the table or stamp Alembic.

## Prerequisites

1. Review draft PR #7 and the migration runner. Confirm the production database is still at `0031_cleanup_retry_limits` and `public.auth_sessions` is absent.
2. In GitHub, open **Settings → Environments** and create `production-migration`. Configure required reviewers if your GitHub plan supports them.
3. Add the environment secret `VERVFY_PRODUCTION_DATABASE_URL` with the **restricted migrator** connection string. Never put this secret in repository files, chat, issues, or workflow logs. Use the project's reviewed Supabase endpoint and SSL verification settings.
4. The workflow requires a verified CA bundle at `/etc/ssl/certs/ca-certificates.crt` and the URL query `sslmode=verify-full&sslrootcert=/etc/ssl/certs/ca-certificates.crt`. If the certificate chain is incompatible, stop and use the reviewed project CA; do not weaken TLS.
5. A workflow_dispatch workflow must exist on the repository's default branch before it can be manually triggered from the Actions UI. **Do not merge this draft PR merely to make it runnable.** First complete code review and focused tests.

## Preflight only

Once reviewed and available on the default branch: GitHub → Actions → **Production auth sessions migration preflight** → **Run workflow**.

The workflow invokes `python scripts/auth_sessions_production_migration.py check --confirm-project-ref ...`. It performs read-only checks and must not run any migration.

If it fails, inspect the failure category without pasting credentials. Do not retry with `postgres`, `service_role`, or `sslmode=require`.

## Separate approval required for migration

The current workflow deliberately has **no upgrade job**. After preflight passes, separately review the exact revision `0031_cleanup_retry_limits..0032_auth_sessions`, the migration code, role privileges, database backup/recovery readiness, and a short-lived authorization. Only then run the guarded runner in an authorized environment and verify `auth_sessions` grants and the Alembic revision.

After the migration, restart/redeploy the API if necessary and test a new login, logout, and invalidated session. Never assume a successful DDL operation proves login works.
