# Phase 4C.2.2 — Operator Foundation Security Audit

**Review scope:** read-only adversarial review of migration 0030, its PostgreSQL
tests and disposable role fixture, migration-chain tests, and directly relevant
runtime/RLS/storage lifecycle controls.

**Environment:** source inspection only; no hosted or production database was
accessed. No files other than this requested report were changed. No additional
database verification was necessary for this review.

## Executive result

No confirmed vulnerability allows an ordinary runtime role to access operator
tables or escalate operator privileges in the currently implemented code. The
operator schema is private, runtime roles have no schema/table grants, the
foundation owner is NOLOGIN and SETtable only by the restricted migration
login, and there is no operator authentication or administrative endpoint yet.

The review did identify security gaps that must be resolved before operator
authentication or provisioning is enabled. These are confirmed schema
behaviors, but their authentication impact is currently theoretical because
there is no code that accepts operator sessions or consumes operator roles.
The foundation owner and migration login remain trusted database maintenance
principals; they are not an independent operator provisioning system.

## Findings

| # | Severity | File | Lines | Vulnerability | Confidence |
|---|----------|------|-------|---------------|------------|
| 1 | 🟡 MEDIUM | `alembic/versions/0030_operator_foundation.py` | 203-226, 358-387 | Revoking a credential does not revoke existing sessions or prevent clearing the credential's revocation timestamp. | 9/10 |
| 2 | 🟡 MEDIUM | `alembic/versions/0030_operator_foundation.py` | 482-489, 23-63 | Audit DML is blocked by triggers, but the table owner can alter/disable triggers; the migration login can SET that owner role. | 9/10 |
| 3 | ⚪ LOW | `alembic/versions/0030_operator_foundation.py` | 260-264, 426-434 | `bootstrap_reference` is caller-supplied evidence text, not a single-use authorization; after an admin is revoked, the reference can be replayed by the owner role. | 10/10 |
| 4 | ⚪ LOW | `alembic/versions/0030_operator_foundation.py` | 337-340, 426-470 | Operator status changes revoke sessions, but leave role assignments active; a future authorizer must check account status on every authorization decision. | 9/10 |
| 5 | 🟡 MEDIUM | `docs/storage-lifecycle.md` | Phase 4C.2.1 section | No independent, individually authenticated production bootstrap/provisioning process exists; direct table provisioning is reachable only through the privileged migration-owner capability. | 10/10 |

Severity describes the pre-enablement risk if the foundation is used as an
operator authentication/provisioning system. Findings 1, 3, and 4 are not
currently exploitable through an application endpoint because no such
authentication or provisioning path exists. Finding 2 is a trust-boundary
limitation for the database owner, not an ordinary-runtime bypass. Finding 5 is
an explicit operational limitation rather than a code exploit.

## Evidence and exploitability

### 1. Credential revocation does not invalidate extant sessions

The session insert/update guard checks that the operator is active and the
credential is unrevoked. It does not guard updates to
`operator_credentials.revoked_at`, invalidate sessions for that credential, or
prevent clearing that timestamp. Existing sessions remain with an unexpired
session digest after credential revocation. If future session-validation code
checks only session expiry/revocation and operator status, a credential revoked
after session issuance could continue to authenticate.

**Affected principal:** holder of a session issued from the revoked credential.
**Current exploitability:** theoretical; no session issuance, validation, or
HTTP authentication code exists. The schema owner is required to change these
rows.

### 2. Audit history is append-only against DML, not against its owner

The migration installs row-level UPDATE/DELETE and statement-level TRUNCATE
triggers, and tests verify those DML operations are rejected even under the
foundation-owner role. However, that role owns the audit table and its trigger
functions. A principal that can SET the owner role can alter/drop the trigger,
change the table, or drop the schema before modifying the audit history. The
migration login is intentionally the only role allowed to SET the owner.

**Affected principal:** migration login / foundation owner. Ordinary application
roles cannot use the schema and cannot perform the bypass. PostgreSQL
superusers/database owners remain trusted administrators.

The current tests therefore prove resistance to ordinary DML, not tamper
evidence against a privileged database administrator. If that stronger
guarantee is required, store or replicate audit evidence to an independently
controlled append-only system.

### 3. Bootstrap reference is not a replay-resistant credential

The role-assignment trigger permits an ungranted `operator_admin` assignment
when no active administrator exists and `bootstrap_reference` is non-null. A
partial unique index allows at most one *active* bootstrap administrator.
Revocation removes that row from the index, and the trigger does not record or
consume reference values. The same text can be reused to bootstrap again after
the current administrator is revoked.

This does not let `app_runtime`, `google_auth_lookup`, or
`storage_cleanup_worker` bootstrap an administrator: they lack schema access.
The caller must already possess the foundation-owner capability. The value is
currently audit metadata, not authorization. Do not treat it as a bearer token
or proof of human approval.

### 4. Role assignments survive account suspension/revocation

Changing an operator to suspended or revoked revokes their extant sessions.
Existing `operator_role_assignments` are not revoked by that transition. No
current code consumes these assignments, so this is not an active privilege
escalation. Any future authorization check must require an active identity and
an unrevoked assignment, and must define whether role revocation also
invalidates existing sessions. Re-enabling a suspended identity must not
silently restore authority unless that is an explicit reviewed policy.

### 5. First-admin provisioning is not operationally safe yet

The migration seeds no operator and hardcodes no credential. It requires a
pre-provisioned NOLOGIN foundation-owner role and restricts SET membership to
the migration login. That avoids ordinary application access, but leaves the
migration login as the only supported way to assume the owner capability.
There is no independent individual bootstrap principal, enrollment ceremony,
or approved two-person process in the current repository. Directly using
migration credentials to provision a real operator would conflate schema
maintenance with human authentication administration.

The missing process is documented in `docs/storage-lifecycle.md`; until it is
implemented and reviewed, no real operators should be provisioned.

## Confirmed protections

- `app_runtime`, `storage_cleanup_worker`, and `google_auth_lookup` receive no
  usage on `vervfy_operator` and no table privileges; tests exercise denied
  access and unauthorized inserts.
- All five operator tables have ENABLE/FORCE RLS and an owner-only policy.
- The foundation owner is NOLOGIN, non-privileged, and has no other role
  memberships or pre-existing object grants. Only `migration_owner` can SET
  it; inheritance and ADMIN are denied. Effective membership checks reject
  other roles.
- No SECURITY DEFINER function is created. Trigger functions are
  SECURITY INVOKER with `search_path=pg_catalog,pg_temp`; PUBLIC function
  execution and schema/table grants are revoked.
- Operator rows have no foreign key or automatic association to ordinary users
  or Google identities. There is no application registration or admin endpoint.
- Bootstrap cannot self-grant, later role grants/revocations require an active
  operator administrator, and partial unique indexes constrain duplicate
  active assignments.
- Suspended/revoked identities cannot receive new sessions, and status changes
  revoke existing sessions. Session digests are 32-byte values rather than raw
  tokens; sessions must reference an unrevoked credential owned by the operator.
- Audit UPDATE/DELETE/TRUNCATE attempts are rejected by triggers, including
  direct DML as the foundation owner.
- The migration graph is linear through `0030_operator_foundation`, with
  `0029_cleanup_retry_limits` as its parent. Migrations 0028/0029 and the
  Phase 4A–4C protections were not modified in this audit.

## Missing security regressions

1. Revoke a credential after issuing a session; verify all existing sessions
   are rejected or revoked, and that credential revocation cannot be undone.
2. Verify a suspended/revoked operator and an operator whose administrator role
   is revoked cannot authorize requests, including when a session already
   exists.
3. Exercise bootstrap replay after revocation and concurrent bootstrap
   attempts. The active-row uniqueness constraint helps concurrency, but
   reference consumption/replay semantics are not tested or implemented.
4. Verify the chosen audit threat model explicitly. Existing tests cover DML
   immutability but not tampering by a database owner who can alter triggers or
   schema objects.
5. Test migration preflight rejection for indirect owner-role membership,
   unexpected default ACLs, and an unsafe migration principal.

## Prioritized remediation plan

1. **Before authentication:** make credential revocation monotonic and ensure
   every session validation checks operator status, credential status,
   unrevoked role assignment, session expiry, and session revocation. Revoke
   existing sessions on credential revocation and role revocation.
2. **Before first production provisioning:** define a separate, individual,
   strongly authenticated, dual-controlled bootstrap process outside ordinary
   runtime and routine migration credentials. Consume bootstrap authorization
   atomically and durably; a free-form reference must remain evidence only.
   Record the external change reference and operator identity without logging
   secrets. If the deployment cannot provide that identity boundary, keep
   production provisioning disabled.
3. **Before claiming tamper-resistant audit:** either explicitly limit the
   guarantee to application/runtime roles and trust the database owner, or
   replicate signed/append-only audit evidence into a separately controlled
   system.
4. **Before authorization is enabled:** add the missing disposable-PostgreSQL
   regressions above, especially credential/session revocation and bootstrap
   replay/concurrency.

## Follow-up remediation status

The selected follow-up was implemented in forward-only migration
`0031_operator_revocation` (`0030_operator_foundation` remains unchanged).
This section supersedes the affected schema-behavior findings above; it does
not claim production readiness.

- **Credential revocation:** updating an active credential to revoked now
  revokes every session referencing it in the same transaction. The database
  rejects any later update to an already revoked credential, including an
  attempt to clear `revoked_at`; credential identity and public key are
  immutable. A disposable-PostgreSQL regression verifies session revocation
  and rejected restoration.
- **Bootstrap replay:** the first `operator_admin` assignment is now single-use
  for the lifetime of the database history, not merely while active. Its
  external reference is unique among bootstrap assignments, and the trigger
  rejects a second bootstrap even with a different reference. A preflight
  refuses upgrade if multiple historical bootstrap assignments already exist.
  The regression revokes the first bootstrap assignment and verifies both
  same-reference and new-reference attempts fail.
- **Audit-owner tampering:** not technically solved. The owner and migration
  login can alter/drop same-database triggers or schema objects. Documentation
  now narrows the guarantee to rejection of direct DML and explicitly does not
  claim owner-resistant/tamper-proof history. An independently controlled
  append-only sink is still required for that stronger property.
- **First-operator provisioning:** only the schema-level first-admin replay
  guard is implemented. No independent individually authenticated,
  dual-controlled bootstrap mechanism exists. Do not provision production
  operators until an independently reviewed bootstrap process is available.
- **Role revocation and authorization:** the previously noted requirement that
  authorization verify current operator status and active role assignments
  remains. No authentication, session validation, administrative endpoint, or
  recovery API was added.

The migration does not rewrite revisions 0028, 0029, or 0030, and does not
create an administrative endpoint, enable physical deletion, or connect to a
hosted database. Validation results for this follow-up are recorded in
`reports/phase4c23-remediation-validation.md`.

## Scope limits

This was a read-only source audit. No test suite was rerun, no database was
connected, and no files except this requested report were changed. Findings do
not establish production readiness. WebAuthn, operator session consumption,
provisioning operations, hosted role provisioning, and independent deployment
review remain outstanding.
