# First production database migration: 0019 to 0028

This packet prepares a separately controlled production migration. It does not
authorize or perform a production connection, migration, role change, deploy,
or Google OAuth enablement. `staging_guard.py` remains staging-only and is not
used or changed by this runner.

## Runner controls

Use only `python -m scripts.production_migration`. It requires the approved
production project reference `llxmskxxchpmeavorusj`, database `postgres`, the
restricted migration role `vervfy_prod_migrator`, a readable CA bundle, and
`sslmode=verify-full`. Direct mode remains the default. Explicit `session`
mode accepts only this project's IPv4-compatible Supabase Session Pooler host
on port 5432; port 6543 (transaction pooling) is rejected. For the pooler URL,
the login must be `vervfy_prod_migrator.llxmskxxchpmeavorusj`, while the
database role checked after connection remains `vervfy_prod_migrator`.
Supabase documents shared-pooler custom-role usernames as
`[ROLE].[PROJECT-REF]`. Both modes reject fallback database URLs and libpq
connection overrides. The runner checks server-reported database/login/TLS,
PostgreSQL version, role graph, exact starting revision, database/schema
capabilities, and ownership of all tables the remaining migrations alter or
grant. The `upgrade` operation holds a session advisory lock, repeats the same
checks in a read-only transaction, then passes that same connection to
Alembic. Alembic production execution through its CLI is blocked by
`alembic/env.py`.

The migration login must be a non-superuser, non-`BYPASSRLS`, non-`CREATEDB`,
non-`CREATEROLE`, non-replication login. It needs database `CONNECT` and
`CREATE`, `public` schema `USAGE` and `CREATE`, and ownership of `public`'s
existing application/cache tables plus `public.alembic_version`. The two
lookup capability roles and `google_auth_lookup` must already exist with the
restricted attributes and exact Supabase/membership graph checked by
`0022_provider_identity_lookup.py` and `supabase_role_memberships.py`. The
runner only verifies these prerequisites; it never creates or modifies roles.

## Required configuration

Inject the database URL from the approved secret store; do not put its password
in shell history, source files, or logs. Set the mode to `direct` or `session`;
omitting it preserves the existing direct-connection behavior. Use the matching
URL form and include the provider-approved CA bundle in its query:

```text
VERVFY_ENVIRONMENT=production
VERVFY_PRODUCTION_CONNECTION_MODE=direct
VERVFY_PRODUCTION_PROJECT_REF=llxmskxxchpmeavorusj
VERVFY_PRODUCTION_EXPECTED_DATABASE=postgres
VERVFY_PRODUCTION_EXPECTED_USER=vervfy_prod_migrator
VERVFY_PRODUCTION_CA_FILE=<provider-approved readable CA bundle path>
VERVFY_PRODUCTION_DATABASE_URL=postgresql+psycopg://vervfy_prod_migrator:<url-encoded-password>@db.llxmskxxchpmeavorusj.supabase.co:5432/postgres?sslmode=verify-full&sslrootcert=<url-encoded-CA-path>
```

For the IPv4-compatible Session Pooler, change only the mode and URL as follows.
The password remains the restricted migration role's password; do not substitute
the `postgres` role or its credentials:

```text
VERVFY_PRODUCTION_CONNECTION_MODE=session
VERVFY_PRODUCTION_DATABASE_URL=postgresql+psycopg://vervfy_prod_migrator.llxmskxxchpmeavorusj:<url-encoded-password>@aws-0-us-east-2.pooler.supabase.com:5432/postgres?sslmode=verify-full&sslrootcert=<url-encoded-CA-path>
```

Unset `DATABASE_URL`, `MIGRATION_DATABASE_URL`, and `PGHOST`, `PGPORT`,
`PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGOPTIONS`, `PGSERVICE`, `PGSERVICEFILE`,
`PGSSLMODE`, and `PGSSLROOTCERT`. The direct URL username is the migration role;
the Session Pooler URL username is that role followed by `.` and the exact
project reference. The runner rejects any other role, project, host, port, or
database, and requires `sslmode=verify-full` plus the configured CA bundle.

## Read-only production check and exact migration command

After the production endpoint, login, TLS CA, permissions, backup, maintenance
window, and independent production approval are verified out of band, the
following check connects read-only and requires revision `0019_track_listens`:

```bash
python -m scripts.production_migration check \
  --confirm-project-ref "$VERVFY_PRODUCTION_PROJECT_REF"
```

Only if that check passes, and only inside the separately approved window, run
the single migration command below. Its authorization is for this exact
revision range and expires after ten minutes; the runner rejects expired or
more-than-15-minute authorizations.

```bash
AUTH_EXPIRES_AT="$(date -u -d '+10 minutes' '+%Y-%m-%dT%H:%M:%SZ')"
python -m scripts.production_migration upgrade \
  --confirm-project-ref "$VERVFY_PRODUCTION_PROJECT_REF" \
  --authorize-production-migration 0019_track_listens..0028_webauthn_enrollment \
  --authorization-expires-at "$AUTH_EXPIRES_AT"
```

The command upgrades exactly to `0028_webauthn_enrollment`, not an unbounded
`head`. It stops on any identity, TLS, privilege, role-graph, revision, or
authorization mismatch. It does not deploy code, change roles, or enable
Google OAuth. Do not retry after an ambiguous connection loss until the
revision and schema state have been independently inspected.

## Rollback and recovery

There is no safe `alembic downgrade` rollback from `0028` to `0019`: revisions
`0023` through `0026` are forward-only, `0021`/`0022` protect account identity
and role state, and `0027`/`0028` refuse to discard retained WebAuthn or
recovery data. Feature rollback means keeping the schema and data, disabling
the feature in application code, and using a reviewed forward repair if
needed. Do not delete records, stamp a revision, or improvise role cleanup.

Before any authorized production execution, require a verified restorable
backup/snapshot and a named recovery owner. On migration error, stop all
retries and deployments. PostgreSQL DDL in this chain is transactional; after
a connection loss, use a separately authorized TLS-verified read-only
connection to inspect `public.alembic_version`. `0019_track_listens` indicates
the transaction did not commit; `0028_webauthn_enrollment` indicates it
committed. Any other version or unexpected objects is an incident requiring
manual reconciliation. Restore from the approved backup only under the
separate recovery decision, with explicit acceptance of data loss since that
backup and a tested restore procedure. Never use downgrade as recovery.

## Current evidence and blockers

The local runner tests and disposable-database migration tests do not establish
production endpoint identity, TLS, revision, role attributes/memberships,
table ownership, privileges, or backup restorability. No production endpoint
was contacted and no hosted migration was run. Those live checks, the approved
migration login/CA settings, and a verified recovery point remain prerequisites
before the command above can be run.
