# Vervfy Phase 4C.2.4 — Independent Audit Trust Boundary and Operator Provisioning Architecture

**Status: design proposal only.** No source, migration, test, or configuration
was changed. No hosted database, real identity, or Storage service was accessed.
This report does not authorize provisioning, operator actions, production
deployment, or physical object deletion.

## 1. Executive summary

The current operator foundation is isolated from ordinary application roles,
but its identity, role, session, and audit records reside in the same
PostgreSQL trust domain as Vervfy's application data. A principal that controls
that database, or can assume the operator foundation owner through the
migration login, can alter the in-database records and their protections.
Migration 0031 makes initial bootstrap history single-use and credential
revocation monotonic; neither feature independently verifies a human
administrator or withstands a malicious database owner.

**Recommendation:** do not make `vervfy_operator` in the application database
the production authority. Establish three separately administered planes:

1. A dedicated operator control plane, with its own deployment identity,
   operator identity/session store, narrowly scoped database capability, and
   a host/origin separate from the music-player account system.
2. An external audit ingress and immutable archive in a security-owned cloud
   account/project, outside the control of application deployers, database
   owners, and operator administrators.
3. An out-of-band bootstrap trust root controlled by at least two of three
   individually identified trustees. Require two active operators for
   sensitive actions and two independent approvals for administrator grants,
   credential recovery, and high-impact recovery decisions.

Every privileged state change must have a durable external audit-intent receipt
before its database transaction begins, and an external outcome event after
the transaction. A missing audit receipt, invalid approval, stale
authorization, or unavailable audit service must fail closed. Hash chaining
and signatures supplement independent retention; they do not replace it or
prove that a compromised producer told the truth.

The existing schema can remain as a local/test foundation or transition
artifact, but it must not become an authenticated production control plane
without independent identity, authorization, provisioning, and audit controls.
WebAuthn, operator sessions, action APIs, recovery, and external audit delivery
are not implemented. Physical Storage deletion remains disabled and must stay
disabled.

## 2. Current security boundaries

Repository evidence describes a Next.js frontend and FastAPI backend on Render,
Redis for sessions/queues, and Supabase PostgreSQL and Storage (`README.md`,
`render.yaml`). `render.yaml` has no operator service or external audit
destination. This is repository configuration evidence only; it is not
verification of current hosted settings.

Ordinary Vervfy accounts use the existing username/password and application
session flow (`auth.py`). They are not operator identities. Migration 0030
creates `vervfy_operator` in the same PostgreSQL database, with forced RLS,
owner-only policies, and no grants to `app_runtime`,
`storage_cleanup_worker`, or `google_auth_lookup`. The foundation owner is
NOLOGIN and the migration principal is the only role allowed to SET it.
Migration 0031 adds a lifetime-unique first `operator_admin` assignment and
credential-revocation session invalidation.

The audit table and its triggers are still in that same database. The triggers
reject direct DML, but the table owner can alter or remove them; the migration
principal can SET the owner role. Thus the current boundary protects against
ordinary runtime SQL access, not against the database owner or migration
principal. No operator WebAuthn ceremony, independent administrative session,
authorization service, audit writer, or production provisioning procedure
exists. `docs/storage-lifecycle.md` keeps manual review/recovery unavailable,
and physical deletion is explicitly disabled.

### Confirmed findings and risk status

| Finding | Evidence/status | Assessment |
|---|---|---|
| Same-database audit protections are mutable by database maintenance principals. | Confirmed by ownership and migration-role SET capability in migrations 0030/0031; audit triggers cover DML, not DDL/object ownership. | Confirmed trust-boundary limitation. No ordinary application-role bypass was found in the foundation tests. |
| Operator identities and authorization share the application database owner boundary. | Confirmed: all five operator tables are in `vervfy_operator` in the same PostgreSQL database as application tables. | A compromised application-database owner can alter identities, credentials, sessions, role assignments, or triggers. |
| First-admin bootstrap has no human-authentication ceremony. | Confirmed: migration 0031 makes the bootstrap row/reference single-use, but `bootstrap_reference` is evidence text and database-owner capability remains the write authority. | Replay through the intended schema path is addressed; human authorization is not. |
| Role assignments outlive suspension/revocation. | Confirmed in migration 0030 and noted in the Phase 4C.2.2 audit. | No current authentication code consumes these assignments. Treat as a future authorization hazard, not a current application exploit. |
| Ordinary runtime roles are isolated from operator tables. | Confirmed by migration grants/RLS and synthetic PostgreSQL tests. | A useful boundary that must be retained, but not a defense against a database owner. |
| Operator authentication and recovery endpoints are absent. | Confirmed by repository inspection; no operator session or WebAuthn service is present. | Passkey theft, malicious-operator abuse, and operator-session bypass are future risks, not currently reachable operator endpoints. |
| No independent audit destination is configured. | Confirmed by repository configuration and reports; no live service configuration was inspected. | The external logging and monitoring controls described below are prospective. |

These are source-level findings, not claims about the live Render or Supabase
deployment. No production endpoint, database, Storage bucket, or user record
was queried.

## 3. Threat model

| Threat actor/event | Current exposure | Required design response and residual risk |
|---|---|---|
| Compromised application runtime | `app_runtime` has no operator-schema grant; no operator API exists. | Keep player sessions and routes out of the admin trust path. A separate control-plane service and database must be the only operator authority. Runtime compromise may still affect ordinary app data. |
| Compromised application PostgreSQL owner | Can control same-database schema objects and is outside forced-RLS protections. The migration login can SET the operator owner. | Move authoritative operator identity/authz out of this database. Independently ship managed database/admin logs. A compromised owner may still alter application data; audit controls detect/report where the provider exposes evidence, but do not prevent arbitrary SQL. |
| Compromised migration credentials | Can assume the operator owner and perform schema-level operations. | Use a separate, short-lived, approval-gated migration principal for schema changes only. Do not use it to create people, credentials, or roles. Capture privileged database and cloud-control-plane actions externally. |
| Compromised operator account or stolen passkey | No operator login currently exists. | Use phishing-resistant WebAuthn with user verification, two registered hardware-backed authenticators where policy permits, short-lived independent sessions, immediate credential/session revocation, action-specific step-up, and dual approval for high-impact actions. A valid passkey still proves key control, not benign intent. |
| Malicious administrator | No current operator administrator can authenticate. | Split review, identity administration, and execution. Prohibit self-grants and self-recovery; require two distinct active operators for sensitive grants and state-changing recovery. Preserve an independent audit copy and alert reviewers. Collusion remains residual risk. |
| Audit destination outage or quota/credential failure | No audit service currently exists. | Fail closed for privileged reads and all state changes requiring audit. Do not fall back silently to the PostgreSQL audit table or an in-memory queue. Alert, retry, and reconcile. An outage delays recovery; this is safer than unaudited action. |
| Bootstrap replay | Migration 0031 blocks a second bootstrap assignment through the schema. | Also use a signed, short-lived, environment- and subject-bound authorization with a unique nonce, atomic consumption, and external audit receipt. A database-only index cannot prove trustee approval. |
| Concurrent bootstrap/provisioning | Migration 0031 has uniqueness and regression coverage for concurrent first-admin grants. | Keep a database uniqueness constraint and transaction/advisory lock around consumption; enforce idempotency at the provisioning service and audit ingress as well. A single winner must be observable externally. |
| Unauthorized privilege escalation | Ordinary runtime access is denied today. | No role inheritance or PUBLIC access; no app/runtime membership in operator roles; narrowly scoped capability roles; fixed search paths for any privileged routine; positive role-graph checks. Re-test effective privileges after every schema change. |
| Audit account/provider compromise | Not present in the repository. | Separate human admins, cloud account/project, IAM root, encryption keys, and backups. Immutable retention limits deletion but cannot protect against provider failure, legal action, account compromise before write, or all authorized misconfiguration. |

## 4. Independent audit infrastructure comparison

### Required event and delivery protocol

The audit record should be a versioned, canonical envelope containing an event
ID, action ID, event type (`intent`, `approved`, `completed`, `failed`, or
`reconciled`), actor and approver operator IDs, credential/key reference
(non-secret), action/resource type and ID, minimized prior/resulting state,
reason, request/correlation ID, authorization-policy version, source service,
source and ingestion timestamps, and any external approval/ticket reference.
Do not include passkey assertions, private keys, session tokens, passwords,
signed URLs, file contents, or unnecessary personal data. Treat target IDs and
reasons as potentially sensitive and apply an approved retention/privacy
policy.

For each mutation:

1. The control plane authenticates the operator, rechecks current status,
   credential, session, role, approval quorum, and target invariants.
2. It sends a uniquely identified intent to the independent audit ingress.
   The ingress validates schema/size, persists it to the immutable destination,
   and returns a signed receipt only after durable acceptance.
3. Only then may the control plane begin the narrowly scoped database
   transaction. The transaction records the receipt/action ID and preserves the
   existing tenant/reference checks, object-before-job lock order, lease/token
   fencing, and lifecycle invariants.
4. The control plane appends an outcome event. Delivery is at-least-once, not
   presumed exactly-once. A stable event ID plus payload digest makes retries
   idempotent. Reusing an event ID with a different digest is an alert.

If the database commits but the outcome event cannot be delivered, the prior
intent remains durable and visibly unresolved. The control plane must stop
further privileged mutations, retry from its separately administered durable
queue, and reconcile against the action ID. It must not report a fully audited
success until the outcome is recorded. Do not rely on an outbox stored only in
the application PostgreSQL database: its owner can alter it.

Use the audit service as the sequencing authority for a single ordered stream
or deterministic shards. Add a previous-event hash and periodically sign
checkpoints with a key controlled by audit custodians, then retain both events
and checkpoints immutably. A hash chain alone is not protection: an actor able
to rewrite every event can recompute the chain; an actor able to use the
signing key can create new signatures. Independent retention and key control
are the essential boundary. A signature attests to the key that signed a
record, not necessarily to the truth of its input.

### Viable approaches

| Approach | Security and integrity | Complexity and operations | Failure modes and fit |
|---|---|---|---|
| **A. Separate security account with S3 Object Lock Compliance archive and a small audit-ingress service.** | WORM retention protects locked object versions; AWS documents that Compliance mode prevents deletion during retention even by the account root. Versioning and a default Compliance retention policy are required. The application cannot delete, shorten retention, change the bucket policy, or control the KMS key. | Highest build/operations burden: implement ingress validation, event-ID deduplication, searchable index, signed receipts/checkpoints, retries, dashboards, key rotation, cost/retention management, and restore drills. Place the account and administrators outside the Render/Supabase application boundary. | S3 Object Lock protects a particular version, not against every new version or delete marker; monitor versions and configuration. Stopped ingestion is a separate failure: heartbeat and delivery alerts plus fail-closed actions are required. Best fit when deletion resistance and independent custody are primary. |
| **B. Separate security project with a locked Google Cloud Logging log bucket.** | Google documents that bucket locking is irreversible and locks the retention policy; use a project with separate administrators and export application/provider audit logs to it. Provides a managed log store and query path. | Less custom storage/search work; still needs an authenticated ingress, event schema, deduplication, signed provenance, and independent approvals. Adds a GCP operational and billing dependency to the Render/Supabase stack. Region selection and retention cannot be treated as casual settings. | Verify actual locked-bucket deletion/retention semantics, API acknowledgment, quotas, export delivery, and organization-admin separation before adoption. A locked bucket cannot recover events never delivered to it. Suitable if Vervfy accepts the GCP dependency and its IAM/retention model. |
| **C. External SIEM/logging SaaS with contracted immutable retention and export.** | Can provide managed search, alerting, and operational support. Security depends on actual tenant-admin deletion controls, retention lock, exportability, and provider audit evidence; “SaaS logging” alone is not immutable. | Lowest custom search/alert burden; recurring cost, vendor integration, data-processing terms, region, account recovery, and retention contract review are required. | Tenant administrators may be able to delete/change data unless an immutable-retention feature is explicitly contracted and tested. Use only if the vendor demonstrates the same independent administration, retention, export, and outage properties as A/B. |

**Recommendation:** use Approach A as the authoritative archive, with an
independently operated audit-ingress service. A separate query/alerting system
may index a copy, but the immutable archive and signed receipts remain
authoritative. AWS S3 is a candidate, not an approved vendor choice: confirm
region, legal/privacy requirements, cost, provider account ownership, and
operational capability first. Do not put the archive in an AWS account
controlled by the same people who hold Vervfy database or deployment
administrator access.

The audit account should have distinct principals:

- **Application deployers:** deploy music and control-plane code; no audit
  read/delete, retention, bucket-policy, KMS, or security-account admin rights.
- **Database operators:** manage PostgreSQL; no audit-account access or
  operator-signing authority.
- **Operator administrators:** perform authorized operator actions; no audit
  retention, archive, signing-key, or database-owner privileges.
- **Audit custodians:** configure retention, keys, alerting, and backup; no
  ability to perform Vervfy operator actions or alter application data.
- **Auditors:** read and verify records; no write, delete, retention, or
  application privileges.
- **Emergency trustees:** at least three individually named people, with
  two-person approval for emergency access; no shared identity.

At least two independent human control groups are required: application/data
operators cannot also be the only audit custodians. Cloud organization/root
recovery must itself be dual-controlled and separately logged. A separate
project in the same organization is not an independent trust boundary if the
same unrestricted organization owner can assume both roles.

### Integrity verification, retention, backup, and alerting

- Verify each receipt signature, canonical payload digest, sequence, and chain
  checkpoint on a schedule and before audit export/review. Store verification
  results and signed checkpoints outside both PostgreSQL and the main archive
  account.
- Alert on gaps, duplicate-ID/digest mismatches, invalid signatures, unexpected
  clock skew, missing control-plane heartbeat, ingestion latency, retry backlog,
  quota/credential errors, and any change to bucket retention, IAM, key policy,
  database ownership, or privileged memberships.
- Use an independently controlled replica/backup in another approved region
  or account. Test restore and integrity verification. Replication is not
  independent if the same principal can erase source and replica.
- Approve retention duration, legal-hold process, region, data minimization,
  and deletion obligations with privacy/legal owners before enabling
  immutability. Locked retention can make later deletion impossible until the
  period expires; do not select a duration by convenience.
- Audit reads and exports as well as writes. Never silently omit events when
  they exceed size, rate, or schema limits; reject, alert, and retain a
  minimized failure record where possible.

## 5. Initial administrator provisioning design

`bootstrap_reference` in migration 0031 is not an authorization credential.
The unique index and concurrency guard prove only that the database accepted
one initial assignment through the intended path. They do not prove who
approved the person or that the migration principal was not misused.

### Viable approaches

| Approach | Security | Complexity/operations | Failure modes |
|---|---|---|---|
| **A. Offline 2-of-3 trustee ceremony with a one-time signed bootstrap authorization.** | Two distinct trustees independently verify the candidate and sign a short-lived authorization bound to the exact environment, operator ID, first-admin role, registration-challenge ID, nonce, and expiry. The actual credential public-key fingerprint is recorded after the WebAuthn ceremony, not assumed in advance. Private trustee signing keys remain individually controlled/offline; the provisioner verifies signatures against pinned public keys. No default administrator or shared password exists. | High initial ceremony and key-custody burden; requires at least three trustees and secure signer verification. Strongest fit for a self-hosted system with no existing trusted admin. | If fewer than two trustees are available, provisioning stops. Lost trustee keys require a separate quorum-controlled key rotation. A compromised provisioner can still deny service or misuse any granted capability; external audit and least privilege remain necessary. |
| **B. Dedicated enterprise IdP group plus supervised WebAuthn enrollment.** | Identity is sourced from a separate enterprise directory; two administrators approve group membership, and each operator separately enrolls an admin-origin passkey. Do not link Google consumer OAuth or an ordinary Vervfy account. | Lower ongoing identity-lifecycle burden if the organization already operates a suitable IdP, but adds IdP federation, group synchronization, account-recovery, and outage dependencies. | IdP superadmins or compromised group provisioning can create operators; the IdP group and its audit must be independently controlled. Not a viable first bootstrap if the IdP itself lacks verified admins. |
| **C. Manual one-time provider-console/DB bootstrap using a temporary privileged database login.** | Can be dual-approved and externally recorded, but still depends on database-owner authority and is difficult to constrain to one authorized identity/credential. It can bypass application authorization and same-database audit triggers. | Operationally simple once a managed DB console exists; requires secure JIT credentials, session recording, role revocation, and postflight review. | Database owner can tamper with operator tables and local audit. This is a last-resort recovery mechanism, not the normal ceremony or a sufficient production trust design. |

**Recommendation:** Approach A for the first operator, followed by two-person,
operator-admin-approved invitations for routine enrollment. Consider Approach
B later only if a verified enterprise IdP and its independent administrative
controls are approved. Do not use C for routine provisioning and do not rely
on unrestricted migration credentials.

### Ceremony and replay/concurrency controls

1. Before provisioning, appoint three named trustees in separate roles and
   verify each person's identity through an independently maintained
   organizational contact/identity process. Require two of three approvals;
   one maintainer cannot satisfy this requirement alone.
2. Create a signed authorization containing a random nonce, exact environment
   and operator-service origin, normalized operator identifier, exact role,
   one-time registration-challenge ID, issue/expiry time, and external ticket.
   Record the enrolled credential's public-key fingerprint only after the
   WebAuthn ceremony succeeds. Do not put a reusable bearer token or credential
   secret in a ticket, command line, SQL, or logs.
3. Verify two distinct trustee signatures and candidate identity out of band.
   Use a WebAuthn registration challenge scoped to the dedicated admin RP ID
   and exact origin. Validate challenge, origin, RP ID hash, user presence and
   verification, credential ownership, and accepted algorithm/metadata before
   persisting the public key. WebAuthn credentials are origin/RP scoped; the
   music-player origin must not share the operator RP ID. See the W3C WebAuthn
   specification.
4. Store the nonce as consumed in the independent provisioning authority and
   enforce a unique database constraint/transaction lock. Consume it
   atomically with the pending identity, credential, first role grant, and
   external audit receipt. A repeated authorization, different payload for the
   same nonce, wrong environment, expired token, or concurrent loser is
   rejected and externally recorded.
5. Keep the identity pending until enrollment and audit confirmation complete.
   Do not automatically promote an ordinary Vervfy user or create a credential
   from Google OAuth. Provision the first human as active only after a second
   admin identity is also established; do not enable high-impact actions with
   one surviving administrator.
6. Disable the bootstrap route/capability after the ceremony. Routine grants
   require an existing active administrator and independent approval;
   administrators cannot grant themselves roles or approve their own
   recovery.

The process must not retain identity-proof documents or other unnecessary
personal data. Record verifier identities, method, time, reason, ticket, and
the credential-enrollment result, not private keys or biometric data. Hardware
security keys and a second separately stored backup key are recommended for
administrators; the accepted authenticator/attestation policy, syncable
passkey policy, and backup procedure require explicit approval.

## 6. Authorization lifecycle

Never authorize an action solely from a historical role assignment, session
claim, JWT, or cached role list. The control plane must synchronously verify
current state for each privileged request: operator is active; credential is
active and belongs to that operator; session is present, unexpired, and not
revoked; required role assignment is current and unrevoked; required approval
quorum is valid; and the action/resource is within the role's scope.

| State | Required behavior |
|---|---|
| **Active** | May authenticate only with an enrolled, non-revoked credential. Each request requires a valid independent operator session and current action-specific role. Sensitive actions require fresh WebAuthn user verification and, where designated, another operator's approval. |
| **Pending / no valid credential** | No login, session, or action. Complete identity verification and credential enrollment before activation. A credential-less active break-glass identity must not be usable. |
| **Suspended** | Deny all authentication and actions immediately; revoke all sessions and role grants in the same audited transaction so reactivation cannot silently restore old authority. Keep credential material only if policy permits; revoke credentials too if compromise is suspected. Reactivation requires fresh approval and new role grants. |
| **Revoked** | Terminal. Deny login/actions; revoke all credentials, sessions, and role assignments. Do not reactivate the same identity; any replacement is a newly verified principal with a new identifier and audited grant. |
| **Credential revoked/missing** | Deny new authentication; invalidate every session bound to the credential in the same transaction. Clearing revocation is never allowed. Replacement requires identity recovery and a new credential enrollment, not restoration of the old key. |
| **Role revoked** | Deny actions requiring that role on the next authorization check. Increment an authorization epoch and revoke all sessions on role changes to avoid stale session claims. Regrant is a new, independently approved assignment. |
| **Session expired or revoked** | Deny immediately. Sessions are separate from music-player/Redis sessions, opaque, server-side, short-lived, Secure/HttpOnly/SameSite, CSRF-protected, and bound to the operator credential and authorization epoch. No silent refresh of revoked/expired sessions. |

Serialize authorization and action state changes against suspension, role
revocation, credential revocation, and session revocation using row locks or an
equivalent linearizable control-plane transaction. An action already committed
before revocation may stand; once revocation commits, no later action may pass
using stale state. Revoke or rotate sessions after any privilege change. Do not
cache authorization for recovery mutations.

The operator service must not bypass existing storage safeguards. Any future
requeue/retain/verification action must preserve tenant isolation, global
reference checks, object/job lock order, cleanup leases, claim-token fencing,
attempt history, and lifecycle invariants. It must never convert provider
verification into deletion completion or grant a direct physical-delete
capability.

## 7. Recovery and emergency access

### Normal operator recovery

- Each operator enrolls two independently held authenticators under supervised
  identity verification. Avoid reliance on email, phone possession, or the
  ordinary player account as the sole recovery proof.
- Loss/theft report: suspend the identity immediately, revoke sessions and
  suspected credential, alert the audit/security contacts, and preserve
  evidence. Two other active operators verify the person through a
  pre-established independent channel, approve a one-time replacement
  enrollment, and record the old/new credential IDs and approvals externally.
- A person cannot approve their own recovery or remove the last other active
  administrator. High-impact role changes and recovery require two distinct
  actors.
- Database credentials, operator passkeys, trustee keys, audit signing keys,
  and audit-retention privileges have separate rotation/recovery procedures.
  Rotating one does not silently re-enable another.

### Loss of all operator access

Use the 2-of-3 trustee ceremony from offline, independently held recovery
material. It may restore operator authentication/provisioning only after
identity verification and an external audit intent. It must not directly
perform storage recovery or deletion. Issue temporary, narrowly scoped access,
record a fixed expiry, rotate/revoke temporary material after use, and require
independent post-incident review.

An audit destination outage is not a reason to bypass audit. Fail closed for
operator inspection if it exposes protected information and for all mutation.
Restore the audit service through its separate cloud-provider recovery process;
record that provider action in the provider's independent control-plane logs
and reconcile before resuming operator work. No emergency path may enable
physical Storage deletion.

## 8. Recommended architecture

1. **Operator identity/control plane:** a separate, minimal admin service and
   database in a security-controlled account/project, separate from Render API,
   Supabase PostgreSQL/Storage, and ordinary account authentication. Use a
   dedicated origin/RP ID, WebAuthn, independent server-side sessions, explicit
   roles, and signed short-lived action authorization. The current
   `vervfy_operator` schema is not authoritative against its database owner.
2. **Privileged action broker:** only this service may request narrowly scoped
   operator database operations. It uses a dedicated non-owner DB capability
   with no membership in app runtime roles. Existing lifecycle SQL
   invariants/fences remain authoritative for storage state. The broker has no
   Storage service key or physical-delete API/permission.
3. **Independent audit service/archive:** a security-owned audit ingress and
   S3 Object Lock Compliance archive (or approved equivalent) in a separate
   cloud account, with versioning, fixed legally approved retention, separate
   KMS/IAM control, signed receipts, event IDs, chain checkpoints, monitoring,
   and independently controlled replica/backup.
4. **Trustee-controlled bootstrap/recovery:** a one-time, 2-of-3 signed
   provisioning authorization plus independent candidate verification;
   post-bootstrap creation requires two active operators. No default admin,
   public registration, player account promotion, or routine migration-login
   use.
5. **Explicit fail-closed policy:** no privileged action or protected
   inspection without a valid external audit receipt and live current
   authorization. No local database/in-memory fallback that produces a
   success-shaped outcome.

Separate accounts alone are insufficient if the same organization root,
employee, static token, or deployment pipeline can control all planes. Access
reviews must test effective IAM/role memberships and emergency access across
all providers.

## 9. Implementation sequence

1. **Governance first:** name independent application/database operators,
   operator administrators, audit custodians, and at least three trustees.
   If fewer than two independent approvers exist, keep provisioning blocked.
2. **Approve policy:** role/action matrix, identity-proofing process,
   passkey/backup policy, 2-person actions, session durations, audit data
   minimization, retention/legal hold, regions, RTO/RPO, and audit-outage
   behavior.
3. **Select and establish audit trust boundary:** create the security-owned
   account/project through an approved process, configure locked retention,
   independent IAM and KMS, write-only ingress, read-only auditors, alerting,
   backup/replication, and provider-admin logs. Verify a synthetic event can be
   ingested, verified, retained, and denied deletion by application/database
   principals.
4. **Design the separate operator control plane:** choose host/origin,
   database/provider, workload identity, signing-key custody, network path,
   role graph, privileged action interface, and boundaries with Render and
   Supabase. Confirm no shared admin/root identity.
5. **Define authoritative state migration:** decide how the local schema
   0030/0031 is retained or retired; ensure there is one authority for
   identities, credentials, sessions, assignments, and consumed bootstrap
   nonces. No real operator data is currently available to migrate.
6. **Implement and test bootstrap/WebAuthn:** establish trustee verification,
   nonce binding/consumption, enrollment, multi-credential recovery, origin/RP
   isolation, and fail-closed failure states. Keep bootstrap disabled outside
   the approved ceremony.
7. **Implement authorization and audit choreography:** current-state checks,
   revocation serialization, 2-person approvals, external intent receipts,
   idempotent delivery/outcome events, retry/reconciliation, and monitoring.
8. **Run adversarial synthetic tests:** app-runtime/database-owner/migration
   compromise cases; role and session revocation races; duplicate/replayed
   bootstrap; audit outage/restore; forged/altered events; missing sequence and
   signature; trustee loss; recovery with no active administrators. Use only
   disposable databases and synthetic objects.
9. **Independent review and drills:** external security review, database/IAM
   privilege graph review, audit restore/integrity drill, operator-loss drill,
   and incident-response exercise. Verify physical-delete permissions remain
   absent.
10. **Separate production approvals:** only after all blockers and approvals
    below are satisfied may production identity provisioning or non-destructive
    manual-review operations be considered. This report does not authorize
    either.

## 10. Outstanding production blockers

- No independent operator control plane/database, WebAuthn ceremonies, or
  administrative sessions exist.
- No human identity-verification process, named trustees, approved
  first-administrator ceremony, or operator recovery process exists.
- No external audit ingress, immutable destination, independent KMS/key
  ownership, signed receipts, retention schedule, backup, or monitoring exists.
- Current `vervfy_operator` identity, role, session, and audit tables are inside
  the application PostgreSQL owner boundary.
- The database owner/migration principal can alter same-database operator and
  audit controls; provider-level SQL/admin logging behavior has not been
  verified.
- Role assignments are not automatically revoked on suspension/revocation,
  and there is no production authorization service to enforce current status.
- Render workload identity support, cross-provider egress, alert delivery,
  provider quotas, audit-service durability/acknowledgment, data region,
  retention cost, and legal/privacy obligations are unverified.
- No production environment, role graph, backup/restore, or incident-response
  process was inspected. This is a repository architecture review only.
- Operator inspection/recovery is not available. Physical Storage deletion
  remains disabled and must remain disabled.

## 11. Explicit approval requirements

Before any implementation that touches production identity or privileged
actions, obtain written approval for:

1. Independent accountable owners for application, database, operator
   administration, audit custody, and trustee recovery; confirm no one person
   can administer all planes.
2. At least three named trustees and the 2-of-3 bootstrap/recovery threshold;
   confirm this is operationally possible for Vervfy's maintainer model.
3. Audit provider/account, region, locked-retention mode/duration, legal basis,
   privacy and data-residency review, KMS custody, backup, and restore process.
4. Operator identity proofing, acceptable authenticators/attestation, second
   key storage, lost-key workflow, and independent recovery contacts.
5. Role/action matrix, two-person approval thresholds, session lifetime and
   revocation guarantees, and treatment of suspension/reactivation.
6. Audit payload fields, retention/deletion policy, outage fail-closed behavior,
   expected availability, RTO/RPO, alert owners, and incident escalation.
7. Database/provider administrative logging, separation of migration access,
   short-lived credentials, and prohibition on routine provisioning through
   migration-owner credentials.
8. Independent security review and synthetic-only approval gates before any
   operator account is provisioned or any recovery function is enabled.

Until these decisions are approved and independently verified, retain the
production provisioning and operator recovery blockers. Do not claim
production readiness.

## 12. Sources

- Repository: `README.md`, `render.yaml`, `auth.py`,
  `alembic/versions/0030_operator_foundation.py`,
  `alembic/versions/0031_operator_revocation_bootstrap_guards.py`,
  `docs/storage-lifecycle.md`, and
  `reports/phase4c22-security-audit.md`.
- AWS, [Locking objects with S3 Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html) —
  WORM version retention, Compliance/Governance modes, and deletion-marker
  behavior.
- Google Cloud, [Cloud Logging buckets](https://cloud.google.com/logging/docs/buckets#locking-logs-buckets) —
  locked log-bucket retention is irreversible; bucket region and retention need
  deliberate selection.
- W3C, [Web Authentication: An API for accessing Public Key Credentials, Level 3](https://www.w3.org/TR/webauthn-3/) —
  relying-party scoped public-key credentials and registration/authentication
  ceremonies.
- NIST, [SP 800-63B-4, Authentication and Authenticator Management](https://pages.nist.gov/800-63-4/sp800-63b.html) —
  authenticator lifecycle and recovery considerations. This report does not
  claim a NIST assurance-level assessment.

External documentation was consulted on 2026-11-07. No external service,
account, or cloud resource was created or accessed.
