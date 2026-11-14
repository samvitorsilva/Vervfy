# Vervfy Supabase staging bootstrap approval

**Status: OWNER-APPROVED — BOOTSTRAP EXECUTED AND VERIFIED**

## Approved scope

The owner approved one staging-only role and database-privilege bootstrap
using the exact SQL below, followed by the required read-only post-bootstrap
preflight. This approval does not authorize credentials, migrations, namespace
setup, deployment, or other hosted changes.

- Approver identity: `samvitorsilva (Vervfy Project Owner)`
- Approval ID: `VERVFY-STG-BOOTSTRAP-20261111-01`
- Reason: Authorize only the hash-bound Vervfy staging role bootstrap
  and its listed database/schema privilege changes on the verified Supabase
  staging project.
- Owner confirmation recorded: `2026-11-11T18:47:47Z`
- Validity (UTC): `2026-11-11T19:00:00Z` through
  `2026-11-12T19:00:00Z` (24 hours; execute only within this interval).
- Decision: **APPROVED BY OWNER IN THIS SESSION**

## Bound target and materials

- Supabase staging project/resource reference: `xgqvwqogdtktgfuubzwk`
- Verified session-pooler endpoint: `aws-0-us-east-1.pooler.supabase.com:5432`
- Database: `postgres`; bootstrap connection identity: `postgres`
  (pooler login form `postgres.xgqvwqogdtktgfuubzwk`)
- Verified server identity: Supabase PostgreSQL 17.11
- TLS: `sslmode=verify-full`; CA file
  `/home/sam/Downloads/prod-ca-2021.crt`
- CA PEM SHA-256:
  `700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7`
- CA certificate DER SHA-256 fingerprint:
  `80:70:25:AD:50:D4:ED:21:9D:2C:9C:7D:29:9C:00:4F:82:4E:B0:0C:F7:F6:5A:FE:F6:07:D0:7B:72:E6:CA:FA`
- Candidate archive:
  `release-artifacts/supabase-pg17-oauth-rc/vervfy-supabase-pg17-oauth-rc.tar.gz`
- Archive SHA-256:
  `0fc5bd26bd4b8245e1fbed2f0e6fb6a1211decdd84f1843d918355021f809aa2`
- Verified candidate manifest:
  `release-artifacts/supabase-pg17-oauth-rc/candidate-manifest.json`
- Manifest SHA-256:
  `b508be0f2ddc9c37fef0febc1f013feb2788a43271c91ac1253fda825a563ad6`
- Verification: manifest checksum passes; all 254 listed source files match
  their recorded sizes and SHA-256 values.
- Bootstrap SQL:
  `source/docs/staging-db-bootstrap-proposal.sql`, SHA-256
  `34170f07883246e9fcb439d6e35883324c6676cb38b1395859ff5b533d4eb63c`

The archive and manifest bind the candidate. Execute only the bootstrap SQL
file above from that candidate; do not copy it into or run it from the dirty
working-tree source. The candidate guard has no `bootstrap` operation; this
manual SQL requires this separate, explicit owner approval.

## Exact bootstrap SQL in scope

Run as the verified staging `postgres` identity, only after all preconditions
below pass. This reproduces the SQL statements in the hash-bound proposal; it
sets no passwords and contains no data reads, `DROP`, or migration statements.

```sql
BEGIN;

CREATE ROLE vervfy_oauth_staging_user LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE app_runtime LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE google_auth_lookup LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE vervfy_identity_lookup_owner NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE vervfy_identity_lookup NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE vervfy_storage_lifecycle_owner NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE vervfy_storage_cleanup NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE storage_cleanup_worker LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT, CREATE ON DATABASE postgres TO vervfy_oauth_staging_user;
GRANT CONNECT ON DATABASE postgres TO app_runtime, google_auth_lookup;
GRANT USAGE, CREATE ON SCHEMA public TO vervfy_oauth_staging_user;
GRANT USAGE ON SCHEMA public TO app_runtime;

GRANT vervfy_identity_lookup_owner TO vervfy_oauth_staging_user
    WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
GRANT vervfy_identity_lookup TO google_auth_lookup
    WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;
GRANT vervfy_storage_lifecycle_owner TO vervfy_oauth_staging_user
    WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
GRANT vervfy_storage_cleanup TO storage_cleanup_worker
    WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;

COMMIT;
```

`storage_cleanup_worker` is intentionally dormant: no password, explicit
database `CONNECT` grant, or worker deployment. Preserve Supabase `PUBLIC
CONNECT`, `PUBLIC TEMP`, and `public` schema `USAGE`; this SQL removes only
`PUBLIC`'s `CREATE` privilege on `public`.

## Preconditions and verification gates

1. Reconfirm this is the isolated staging project, exact pooler host/port,
   database and login above. Connect with `verify-full` and the CA whose file
   digest is recorded above. Keep all passwords in the approved secret channel;
   none belong in this record or SQL.
2. Verify archive, manifest, and bootstrap SQL hashes against this record. Stop
   if any byte differs.
3. Before DDL, perform a read-only identity and catalog inventory. Require
   `current_database() = 'postgres'`, `session_user = current_user = 'postgres'`,
   PostgreSQL 17.11, all eight Vervfy roles absent, and no
   `public.alembic_version`, `vervfy_auth`, or `vervfy_storage`. Confirm the
   provider schema/ACL baseline is the reviewed Supabase baseline. Any existing
   Vervfy role/object or unexpected state means stop and separately review;
   do not reuse, alter, or clean it up.
4. Execute the exact bootstrap file with `ON_ERROR_STOP` enabled. Its `CREATE
   ROLE` statements intentionally fail on a pre-existing role.
5. Before any migration, provision required login passwords only through a
   separately approved secret workflow. Then separately approve and run
   `source/docs/staging-migration-default-privileges.sql` as
   `vervfy_oauth_staging_user` (SHA-256
   `dc1d796c86bac26308058bc59eee5257b6b1dee055e71abbfbaf55ea37865e0b`).
   That transaction revokes API-role table/sequence defaults and `PUBLIC` and
   API-role function execution defaults for the migration creator.
6. Run the candidate's read-only
   `source/docs/staging-alembic-preflight.sql` before considering a migration
   (SHA-256
   `0b10da71d00c31f58bd2205da52d046bef2be928f6cbb617b4d289c2abaa8fd4`).
   Require its exact identity, schema, version, role-attribute, membership,
   database/schema privilege, and default-ACL assertions to pass; review its
   complete role, ACL, membership, schema, and settings reports. It must remain
   read-only and end with `ROLLBACK`. Stop on any mismatch.

Expected role contract: all eight roles are non-superuser, non-`BYPASSRLS`,
non-`CREATEDB`, non-`CREATEROLE`, non-replication. Only the migration,
application, Google lookup, and dormant cleanup-worker roles can log in; all
have `NOINHERIT`. The migration role alone receives database/schema `CREATE`;
`app_runtime` receives database `CONNECT` and `public` `USAGE`; Google lookup
receives database `CONNECT` but no direct `public` schema grant. Preserve the
provider's `PUBLIC` schema `USAGE`. The four explicit Vervfy memberships must
have exactly the options in the SQL above. Also require only the reviewed
Supabase-created membership edge for each new role
(`member=postgres`, `grantor=supabase_admin`, `ADMIN=true`, `INHERIT=false`,
`SET=false`); any additional membership fails review.

## Transaction and approval boundaries

The role bootstrap is one transaction. If it fails before `COMMIT`, stop and
roll back/disconnect; verify the baseline again. Once committed, there is no
approved automatic inverse: do not `DROP ROLE`, revoke unrelated Supabase
privileges, or improvise cleanup. Stop and obtain a separate recovery approval.
Default-privilege hardening is a later, separate transaction and approval; if
committed, likewise stop on failure rather than assuming it was reversed.

This approval excludes migration `0027` or `0028`, namespace grants or
initialization, postflight, password assignment, app/worker deployment, OAuth
activation, and all other SQL. Namespace grant/revoke proposals are separately
hash-bound in the candidate and require separate approval after migration
`0027`. No migration or namespace SQL is authorized by this approval.

## Owner confirmation

**Exact statement confirmed:**

> I, `samvitorsilva (Vervfy Project Owner)`, approve
> `VERVFY-STG-BOOTSTRAP-20261111-01` for the reason “Authorize only the
> hash-bound Vervfy staging role bootstrap and its listed database/schema
> privilege changes on the verified Supabase staging project,” valid from
> `2026-11-11T19:00:00Z` through `2026-11-12T19:00:00Z`. Execute only the
> hash-bound role bootstrap SQL in this record against staging project
> `xgqvwqogdtktgfuubzwk`, endpoint
> `aws-0-us-east-1.pooler.supabase.com:5432`, database `postgres`, using the
> recorded `verify-full` CA, candidate archive, and manifest. This approval
> does not authorize password assignment, default-privilege SQL, migrations,
> namespace setup, deployment, OAuth activation, or other SQL.

The owner confirmed the complete statement in this session at
`2026-11-11T18:47:47Z`. This records approval but is not a cryptographic
signature. The execution outcome is recorded below. Approval is valid only
within the listed window; refresh the start and expiry if execution will occur
outside it.

## Execution attempt

At `2026-11-11T19:00:05Z`, client `verify-full` TLS passed, but the combined
staging identity/catalog precondition gate did not pass. Execution stopped;
the bootstrap SQL was not run and no database state was changed. Do not retry
until the failed read-only gate has been reviewed.

At `2026-11-11T19:09:08Z`, the corrected precondition used
`server_version_num = 170011`; approval, all recorded hashes, staging identity,
TLS, and catalog checks passed. The exact hash-bound bootstrap transaction
committed. Separate read-only verification passed for all eight role
attributes, the exact 12-edge membership graph, approved database/schema
grants, revoked `PUBLIC CREATE` on `public`, and absence of migration objects.
The first composite post-check query did not return a complete result; no
corrective action was taken, and the separate read-only checks above then passed.
No passwords, default privileges, migrations, namespaces, deployment, or OAuth
were changed. The full migration preflight remains required before any later
migration; it was not run as part of this bootstrap.

## Next-phase approval request — pending owner confirmation

**Status: OWNER-APPROVED — EXECUTION NOT YET STARTED**

- Proposed approval ID: `VERVFY-STG-CREDENTIALS-DEFAULTS-20261111-01`
- Approver: `samvitorsilva (Vervfy Project Owner)`
- Reason: Authorize only staging login credential provisioning and
  default-privilege hardening for Vervfy's Supabase PostgreSQL 17 release.
- Proposed validity (UTC, 24 hours):
  `2026-11-11T19:14:00.067Z` through `2026-11-12T19:14:00.067Z`.
- Staging project: `xgqvwqogdtktgfuubzwk`
- Endpoint: `aws-0-us-east-1.pooler.supabase.com:5432`; database `postgres`
- Pooler logins: `postgres.xgqvwqogdtktgfuubzwk` for password provisioning;
  `vervfy_oauth_staging_user.xgqvwqogdtktgfuubzwk` for default ACL SQL.
- TLS: `sslmode=verify-full`; CA
  `/home/sam/Downloads/prod-ca-2021.crt`, SHA-256
  `700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7`.
- Candidate archive SHA-256:
  `0fc5bd26bd4b8245e1fbed2f0e6fb6a1211decdd84f1843d918355021f809aa2`;
  manifest SHA-256:
  `b508be0f2ddc9c37fef0febc1f013feb2788a43271c91ac1253fda825a563ad6`.
- Exact SQL: `release-artifacts/supabase-pg17-oauth-rc/source/docs/staging-migration-default-privileges.sql`,
  SHA-256
  `dc1d796c86bac26308058bc59eee5257b6b1dee055e71abbfbaf55ea37865e0b`.

**Proposed exact scope:** Set distinct passwords only for
`vervfy_oauth_staging_user`, `app_runtime`, and `google_auth_lookup`, using
hidden `psql \password` prompts and storing values only in the staging secret
store. Then run only the exact hash-bound SQL above as
`vervfy_oauth_staging_user`. The SQL is one transaction and revokes default
table/sequence grants to `anon`, `authenticated`, and `service_role`, plus
default function `EXECUTE` for `PUBLIC` and those API roles, for objects this
migration role creates. Leave `storage_cleanup_worker` without a password.
Stop on any identity, TLS, approval, hash, permission, or SQL mismatch.
Verify the three logins without exposing credentials and inspect the resulting
default ACLs read-only.

This request does not authorize role or membership changes, any other SQL,
migrations, namespace setup, postflight beyond the stated read-only checks,
deployment, worker activation, OAuth activation, or production access. Password
changes are separate persistent actions; if one fails, stop and record which
roles were completed. The SQL transaction rolls back on pre-commit error; after
commit, do not improvise a reversal—obtain separate recovery approval.

**Exact owner statement confirmed:**

> I, `samvitorsilva (Vervfy Project Owner)`, approve
> `VERVFY-STG-CREDENTIALS-DEFAULTS-20261111-01` for the reason “Authorize only
> staging login credential provisioning and default-privilege hardening for
> Vervfy's Supabase PostgreSQL 17 release,” valid from
> `2026-11-11T19:14:00.067Z` through `2026-11-12T19:14:00.067Z`. I authorize
> setting distinct passwords only for `vervfy_oauth_staging_user`,
> `app_runtime`, and `google_auth_lookup` through hidden prompts and staging
> secret storage, then executing only
> `staging-migration-default-privileges.sql` with SHA-256
> `dc1d796c86bac26308058bc59eee5257b6b1dee055e71abbfbaf55ea37865e0b` against
> Supabase staging project `xgqvwqogdtktgfuubzwk`, endpoint
> `aws-0-us-east-1.pooler.supabase.com:5432`, database `postgres`, using the
> recorded `verify-full` CA and candidate archive/manifest. No password may be
> recorded in documentation or logs. `storage_cleanup_worker` remains without
> a password. This authorization excludes all other SQL, migrations, namespace
> setup, deployment, worker activation, OAuth activation, and production access.

The owner confirmed the exact statement above by replying “confirm” in this
session at `2026-11-11T19:16:57.055Z`. This records approval but is not a
cryptographic signature. No execution result is recorded yet.

### Pre-execution validation

At `2026-11-11T19:18:40.183Z`, the archive, manifest, default-privilege SQL,
and CA hashes matched this record. The staging project-reference login,
endpoint, database, `postgres` identity, and `server_version_num=170011` were
confirmed read-only; a libpq connection with `sslmode=verify-full` and the
recorded CA succeeded. An initial diagnostic also queried `pg_stat_ssl` and
reported `ssl=false`; the candidate explicitly documents that this reports the
pooler-to-server leg, not client TLS. It was not used as a TLS verdict; the
separate client-side `verify-full` connection succeeded. No credentials were
set and no SQL or other database changes were executed. Credential provisioning
is blocked pending an approved staging secret-store destination and secure
write path; no password values are recorded here.
