# Minimal production inspector setup — conditional proposal, not authorization

Project: **llxmskxxchpmeavorusj**. Expected database: **postgres**; reported verified
PostgreSQL: **17.11**. Baseline: `dd22f18b92e26a59d342a98e06dfc2888c58905b`.
No production connection, hosted SQL, role creation or configuration change was made.
The candidate and the existing preflight package remain unchanged.

## Exact next action: approve the absence check first

The Roles dashboard is not authoritative proof of absence. Obtain **Approval A**
for a named project owner/operator to run **only `00-confirm-absence.sql`**, in the
SQL Editor's existing `postgres` session after checking the exact project header.
This is an explicit, narrow exception to the earlier inspection instructions:
the elevated session is used only for this frozen catalog-only check, not general
inspection, object access or provisioning. The script uses `BEGIN READ ONLY`,
only pg_catalog metadata and `ROLLBACK`; it returns no user records or credentials.
It contains no role/grant/configuration writes. It has one result set.

Interpret the result:

- `expected_database` and `expected_pg_17_11` must be true; otherwise STOP.
- `inspector_exists=false` confirms the name is absent from the cluster's role
  catalog without modifying production. If true, STOP creation and have the owner
  review the existing role under the existing approved read-only procedure.
- Any `public_database_create`, `public_database_temp`, nonzero
  `public_large_object_write_routines`, or `automatic_creator_admin_edge_expected`
  means **STOP the strict new-role path before DDL**. The setup transaction would
  reject these conditions; do not run it merely to demonstrate that rejection.
- This does not enumerate/audit all alternative roles. The project owner must
  attest from existing access records that no already-approved suitable inspection
  identity exists; do not create a duplicate or adopt an application credential.

## Important Supabase limitation

Supabase documents that new roles receive PUBLIC privileges including TEMP and
large-object creation; NOINHERIT does not remove PUBLIC access. Some enabled
extensions can additionally expose queue data/routines. Revoking a privilege
from the new role does not override a PUBLIC grant. Supabase advises against
removing provider-required PUBLIC privileges. The strict setup also refuses
CONNECT to any other connectable database, including template1, because its
separate object privileges have not been reviewed. PUBLIC template1 CONNECT
is another documented Supabase default that a new-role-only grant cannot deny.

Also, PostgreSQL 17 gives a non-superuser CREATEROLE creator an automatic ADMIN
edge in the role it creates. That does **not** give the inspector membership in
an elevated role, but the existing preflight runner deliberately rejects inbound
as well as outbound edges. We preserve that existing contract here.

Therefore, **a generally usable, strictly isolated LOGIN cannot be promised on
Supabase under the current no-existing-permission-change constraints**. Default
read-only mode and connection limits do not resolve this. If Approval A confirms
these conflicts, stop for a separately reviewed access design/provider-supported
inspection method. Do not revoke PUBLIC/provider permissions, grant superuser,
weaken the runner, use service_role, or silently substitute an elevated login.
The files below are a conditional, all-or-nothing proposal, not a workaround.

## Approval B: conditional provisioning and credential activation

Only if all absence-check prerequisites pass, an independently authorized owner
may approve the exact hash of `10-create-inspector.sql`, project/database, operator,
window, credential expiry and custody. The operator must already have CREATEROLE
and authority to grant CONNECT, public-schema USAGE and the revision-column grant.
Lack of authority is STOP; never borrow application credentials or add privileges.

The SQL Editor-compatible transaction contains these minimal new-role changes:

```sql
CREATE ROLE vervfy_prod_inspector
 LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE
 NOREPLICATION CONNECTION LIMIT 1 PASSWORD NULL;
GRANT CONNECT ON DATABASE postgres TO vervfy_prod_inspector;
GRANT USAGE ON SCHEMA public TO vervfy_prod_inspector;
GRANT SELECT (version_num) ON TABLE public.alembic_version TO vervfy_prod_inspector;
ALTER ROLE vervfy_prod_inspector SET default_transaction_read_only = on;
```

**Do not execute this excerpt alone.** The actual file wraps it with preconditions,
full effective-privilege assertions and one transaction. Catalogs need no new
`pg_read_all_data`, monitoring-role or blanket SELECT grant. No Storage grants,
RLS policies, functions, migration capabilities or application table grants are
created. PUBLIC/provider/application ACLs and existing role memberships are never
changed. The read-only default is an accident guard, not an access-control boundary.
Checks describe the current privilege state; future PUBLIC grants can change it.
Coordinate a stable ACL/schema window and recheck the contract before Approval C.

The postconditions reject effective user-record reads, all non-release table or
column reads, writes/maintenance, sequence rights, database/schema creation,
unreviewed cross-database access, callable non-catalog/large-object write routines,
unsafe attributes and any role membership edge. An absent/non-plain/RLS-protected
revision table is STOP, not permission to create, stamp or alter it.

After explicit Approval B, paste **the entire `10-create-inspector.sql` file** into
the exact project's SQL Editor and run once as the authorized provisioning role.
Any error means STOP and issue only `ROLLBACK;` if the session remains open; never
execute a standalone COMMIT or selected partial statements. Do not automatically
retry or turn failure into an ALTER/reuse operation. Successful commit leaves a
LOGIN with **no password**; password authentication remains unusable.

Only after complete success and within Approval B's credential-activation scope,
use an authorized direct TLS psql session for the provisioning operator. Existing
provisioner credentials stay in a private operator-owned mode-0600 passfile:

```bash
env -i PATH=/usr/bin:/bin \
 PGHOST=db.llxmskxxchpmeavorusj.supabase.co PGPORT=5432 PGDATABASE=postgres \
 PGUSER=postgres PGPASSFILE=/absolute/private/path/provisioner.pgpass \
 PGSSLMODE=verify-full PGSSLROOTCERT=/absolute/path/approved-project-ca.crt \
 PGGSSENCMODE=disable PGCONNECT_TIMEOUT=10 \
 /usr/bin/psql -X --no-password --set=ON_ERROR_STOP=1 \
 --set=HISTFILE=/dev/null --set=inspector_expiry='<APPROVED_UTC_EXPIRY>'
```

In that interactive session, after checking the operator identity/project record:

```text
SET password_encryption = 'scram-sha-256';
ALTER ROLE vervfy_prod_inspector VALID UNTIL :'inspector_expiry';
\password vervfy_prod_inspector
\quit
```

This changes only the newly approved role and this provisioning session. Never
paste a password into SQL Editor, JSON, command arguments, history, chat or logs.
The hidden `\password` prompt avoids plaintext SQL/history; keep the new secret
in the approved secret store and a separate inspector-owned private passfile.
Do not share either passfile or use a Supabase service-role/API key. PostgreSQL
password expiry limits password authentication, not already-open sessions; any
later disable/drop/cleanup requires its own approved operation. Stop if the
provider's actual provisioning identity differs from the approved `postgres`
identity or cannot perform the exact authorized operations.

## Approval C: later read-only inspection, separately authorized

Provisioning approval does **not** authorize login/inspection as the new role.
Approval C must name the operator, project/database, inspector identity, exact SQL
and hashes, expiry and allowed output. First perform the dedicated identity and
revision verification below; then, after signoff, use the existing catalog-stage
runner/approval record. Never `SET ROLE` from postgres as a substitute for login.

```bash
cd /home/sam/vervfy-latest
env -i PATH=/usr/bin:/bin \
 PGHOST=db.llxmskxxchpmeavorusj.supabase.co PGPORT=5432 PGDATABASE=postgres \
 PGUSER=vervfy_prod_inspector PGPASSFILE=/absolute/private/path/inspector.pgpass \
 PGSSLMODE=verify-full PGSSLROOTCERT=/absolute/path/approved-project-ca.crt \
 PGGSSENCMODE=disable PGCONNECT_TIMEOUT=10 \
 PGOPTIONS='-c default_transaction_read_only=on -c search_path=pg_catalog' \
 /usr/bin/psql -X --no-password --set=ON_ERROR_STOP=1 --set=VERBOSITY=terse \
 --file=release-artifacts/minimal-production-inspector/20-inspector-readonly.sql
```

Require correct direct identity/database, TLS true, version matching the approved
17.11 record, read-only transaction, one recognized revision no later than 0027,
restricted attributes, zero memberships and successful effective-access checks.
No error, empty/multiple revision result, unexpected version or 0028 is a pass.
The version-name regex is only a display safeguard; compare the returned revision
with the candidate's exact 0001–0027 chain via the existing catalog runner before
accepting it. Do not run writes or SELECT user rows as a production permission
probe. Verification queries use only system catalogs and `version_num`.

For the complete existing approved inventory, create an updated **copy** of the
old resource record, not an edit to its frozen template. Confirm all project,
operator, CA, migration-role and hash fields; set `inspection_identity_preprovisioned_and_reviewed`
only after the preceding results and authorize `catalogs` only. Set current revision
to the observed approved value. Then use the exact `preflight.py run-read-only
--stage catalogs ...` command in `../supabase-production-preflight/README.md`.
This role intentionally cannot run the Storage metadata stage.

## Local validation and scope

`test_local_setup.py` uses only a caller-created disposable Unix-socket PostgreSQL
cluster, with TCP disabled and no database environment credentials. Eleven tests cover
revision/catalog read access, denial of user reads and writes even after disabling
the read-only default, missing/existing role handling, exact transaction rollback,
PUBLIC TEMP/large-object/function/read/write/cross-database exposure and non-superuser creator
membership. **All 11 tests passed on PostgreSQL 18.6.** Exact 17.11 was unavailable
locally, so this is not an assertion of a 17.11 runtime test or hosted compatibility.

The success fixture removes PUBLIC privileges **only in the disposable test DB**.
Those fixture operations are not production instructions and demonstrate why a
passing synthetic setup cannot be treated as proof that Supabase defaults pass.
Local fixture user rows/password-null catalog assertions are synthetic and never
part of hosted verification. No backend audits or release tests were repeated.

## Sources

- [Supabase PUBLIC privileges and ineffective restrictions](https://supabase.com/kb/troubleshooting/custom-role-inherits-privileges-that-were-not-explicitly-granted-ddaa1c).
- [PostgreSQL 17 role attributes and automatic creator membership](https://www.postgresql.org/docs/17/role-attributes.html).
- [PostgreSQL 17 role creation](https://www.postgresql.org/docs/17/sql-createrole.html).
- [PostgreSQL secure password handling](https://www.postgresql.org/docs/17/auth-password.html).

**Approval order: A — targeted read-only absence/compatibility check; B — conditional
role provisioning and credential activation; C — later read-only catalog inspection.
No phase authorizes the next. Next action is to approve A only.**
