# Staging endpoint approval boundary

This procedure supersedes the direct psql/Alembic commands and TLS=require setup in the earlier staging review and recovery packet. No hosted execution is authorized by these instructions.

## Independent approval

1. The release owner independently checks the isolated Render resource ID, its exact direct DNS hostname, PostgreSQL port 5432, database `vervfy_oauth_staging`, and migration/app/lookup principals against the staging resource inventory. Never infer staging from a name suffix. Record that evidence privately. This implementation does not query Render or independently prove a resource ID maps to a hostname.
2. For `verify-full`, obtain the trusted CA certificate bundle for that endpoint independently, and verify its source and SHA-256. For an approved `require` exception, CA evidence is optional; if supplied, it must meet the same file/hash checks. TLS defaults to `verify-full`: CA trust AND certificate hostname matching. Only the explicit, expiring Render exception below permits `require`. Render endpoint certificate/CA compatibility has NOT been verified here. If an internal endpoint's certificate does not validate for its hostname, STOP; use a separately approved certificate-valid direct endpoint. Do not downgrade TLS without that exception or use hostaddr to bypass hostname checks. DNS resolution is done by the driver at connection time; matching addresses is not a substitute for certificate authentication.
3. Review the changed env.py, staging_guard.py and tests. Build a NEW artifact in a new location, including staging_guard.py in addition to all existing 32 files. Update the packaging/verification allowlist as described below. Preserve the previous verified artifact unchanged. Independently inspect archive members, each manifest hash, the complete 26-revision chain and exact execution source match. Record the NEW archive and manifest SHA-256 in the approval record.
4. Create an approval JSON outside the checkout with these required fields (and only the optional `tls_exception` described below): `hostname`, `port` (integer 5432), `database` (`vervfy_oauth_staging`), `resource_id`, `archive` (absolute path), `archive_sha256`, `manifest` (absolute path), `manifest_sha256`. Add both `ca_file` (absolute path) and `ca_sha256` for `verify-full`; for the approved `require` exception, either include both or omit both. No passwords go in this file. Approver independently authenticates the JSON's SHA-256 and provides it through the approval channel. Local possession of an arbitrary JSON/digest pair is not independent authorization.
5. Bind explicit hosted approval to that JSON digest, resource identity and both new artifact digests. Approval of the previous artifact does NOT approve the changed execution code.

Historical evidence, retained unchanged:

- Archive: `65170a3ce6d35c2c08b49620c5222c228ebd3f82add07a9d6dbfe364e32d0c92`
- Manifest: `d01c09e318a779c1ac74009c7de62c87e674e9bb7027443f6cb96076e525309e`

## Prepared commands (no execution approval implied)

Use a clean, reviewed runner with the locked dependencies and no ambient PG* variables, SSL_CERT_FILE or SSL_CERT_DIR. Do not source production configuration. No shell tracing. Inject URLs through the staging secret store, never command arguments:

- `VERVFY_ENVIRONMENT=staging` exactly.
- `STAGING_APPROVAL_FILE`: approved JSON path.
- `STAGING_APPROVAL_SHA256`: independently supplied approval digest.
- `DATABASE_URL`: app_runtime login.
- `MIGRATION_DATABASE_URL`: vervfy_oauth_staging_user login.
- `GOOGLE_IDENTITY_LOOKUP_DATABASE_URL`: google_auth_lookup login.

Each URL must use `postgresql://` or `postgresql+psycopg://`, the exact approved lowercase DNS hostname, explicit `:5432`, `/vervfy_oauth_staging`, a nonempty password, and ONLY the approved query parameters: `sslmode=verify-full` (or `require` under the exception), `gssencmode=disable`, and `sslrootcert=<URL-encoded absolute approved CA path>` if and only if CA fields are present (so GSS encryption cannot replace certificate-verified TLS). Percent-encode passwords correctly; no username/hostname encoding, multi-host lists, service files, hostaddr, options, fragments or duplicate query parameters are permitted. Do not replace DATABASE_URL with the migration login. The guard validates all three URLs before any connection.

```bash
cd /home/sam/vervfy-latest
# Safe local validation only; no database connections:
.venv/bin/python staging_guard.py check
# Only after explicit hosted approval:
.venv/bin/python staging_guard.py preflight
.venv/bin/python staging_guard.py upgrade
.venv/bin/python staging_guard.py postflight
```

The psql child receives host, port, database, user, password and approved TLS settings derived from the validated migration URL; it cannot silently use a different PG environment or service. Alembic validates before importing db.py and uses the validated migration URL. The guard checks approved execution-file hashes on every invocation. Postflight criteria and recovery-baseline acceptance remain those in the recovery packet. Keep OAuth disabled and API/workers stopped.

Local development and production env.py behavior is unchanged. This is a fail-closed staging workflow, not an OS sandbox: a user able to alter environment/code can intentionally select a different workflow. Only the guarded staging entry points above are authorized; do not unset the staging marker or call raw psql/Alembic to evade rejection. The guard does not attest deployed service secret separation; confirm the application is never given migration credentials.

## Remaining gates

No new approval JSON or guarded artifact has been approved. CA trust evidence is required for `verify-full` or when CA fields are included in a `require` approval. Thus guarded hosted execution must currently fail. All applicable live TLS, database-role, default-ACL and resource-identity evidence still requires the approved operator workflow. No Render lookup or database connection was performed to establish these assumptions.

## Optional isolated Render staging TLS exception

The same approval JSON may include `tls_exception` with exactly these fields:

```json
{
  "provider": "render",
  "isolated_staging": true,
  "sslmode": "require",
  "expected_roles": {
    "MIGRATION_DATABASE_URL": "vervfy_oauth_staging_user",
    "DATABASE_URL": "app_runtime",
    "GOOGLE_IDENTITY_LOOKUP_DATABASE_URL": "google_auth_lookup"
  },
  "approver": "REPLACE with accountable approver identity",
  "risk_acceptance": "REPLACE with explicit acceptance of missing hostname authentication, isolation evidence and approval reference",
  "approved_at": "YYYY-MM-DDTHH:MM:SSZ",
  "expires_at": "YYYY-MM-DDTHH:MM:SSZ"
}
```

This is a template, not an approval. UTC timestamps must bound the current time,
with a maximum seven-day approval window. Expiration is checked on every guarded
invocation, including Alembic; it does not terminate a connection already running.
The outer approval binds the exact resource ID, hostname, port, database, optional CA and
artifact hashes. The resource ID must have Render's `dpg-` form and the hostname
must be a direct `dpg-….<region>-postgres.render.com` endpoint. These syntax checks
do not prove isolation or the resource-to-host mapping: the approver must verify
both independently. Custom domains, internal hosts and poolers are excluded.

With this approval, all three URLs must use `sslmode=require` instead of
`verify-full`; every other URL restriction remains. CA configuration has two
explicit choices:

- Omit both `ca_file` and `ca_sha256` from the approval and omit `sslrootcert`
  from all three URLs. Preflight/postflight omit `PGSSLROOTCERT` as well. No CA
  evidence is required for this approved encryption-only exception.
- Include both CA fields and use the exact approved `sslrootcert` in all three
  URLs. The file must exist and match its approved SHA-256, just as with
  `verify-full`; preflight/postflight pass the same path to psql.

Partial, empty, malformed or mismatched CA configuration is rejected, including
an unapproved or empty `sslrootcert` URL parameter. There is no fallback from
an approved CA to CA-free TLS. Use the same clean runner for every step: libpq
may still consult its default local root certificate when no explicit path is
provided, so an ambient root certificate can cause certificate validation or a
connection failure. The guard does not disable that driver behavior.

libpq can verify the CA with `require` when a root CA is supplied, but **`require` encrypts traffic and does not provide equivalent
hostname authentication to `verify-full`**. A certificate for another hostname
may be accepted. Document acceptance of that impersonation risk for disposable,
isolated staging with staging-only credentials/data. This exception never applies
to production and does not change RLS, role permissions or OAuth settings.

Preflight and postflight derive the same mode from this approval as Alembic.
Their server-side TLS checks prove encryption, not hostname authentication.
Missing, malformed, future-dated, expired or overlong approvals fail closed;
there is no automatic fallback. To restore `verify-full`, remove the exception,
supply the mandatory CA fields, update all three URLs, and obtain approval for the new JSON digest. No actual
exception or hosted execution approval has been supplied by this local change.
