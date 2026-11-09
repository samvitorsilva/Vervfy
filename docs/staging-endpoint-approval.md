# Render staging endpoint and preflight authorization

**Status (2026-11-07):** The owner adopted the solo-maintainer staging policy
at 2026-11-07 14:50:47 UTC. This is governance adoption, not authorization for a
database connection. The first read-only preflight remains **NO-GO** until its
operation-specific authorization and private staging connection material are
complete. Production Google OAuth remains disabled.

## Endpoint evidence

The owner reports the Render dashboard identifies the isolated staging
resource as:

| Field | Reported value |
|---|---|
| Resource ID | `dpg-dbl7q66tlv9c73b883jg-a` |
| Internal hostname | `dpg-dbl7q66tlv9c73b883jg-a` |
| External TLS hostname | `dpg-dbl7q66tlv9c73b883jg-a.oregon-postgres.render.com` |
| Port / database | `5432` / `vervfy_oauth_staging` |
| PostgreSQL / status | `18` / `Available` |
| Default migration username | `vervfy_oauth_staging_user` |

The owner reports independently comparing the external hostname with Render's
external connection details. This is operator-reported identity evidence, not
a live TLS handshake or database-role check. The internal hostname is not an
external TLS hostname and must never be substituted in a connection URL.

Render Support confirmed external PostgreSQL supports `sslmode=verify-full`,
the endpoint uses Let's Encrypt certificates, and the standard system CA store
is sufficient. No Render-specific CA bundle or server/intermediate
certificate pinning is required.

On the current local runner, the system CA bundle was verified at
`/etc/ca-certificates/extracted/tls-ca-bundle.pem`:

- SHA-256: `9a9c1b798f6ae057ecb84545704e38c89e10f3db5519b24cd4647a1bb2dbf299`
- Root-owned, mode `0444`, 118 PEM certificates.

This confirms the file and digest on this runner only; it does not prove a
Render certificate handshake. Recheck the path and hash if the authorized
execution runner differs.

## Artifact and migration inventory

The new development artifact is outside the frozen release tree at
`~/.copilot/session-state/c71be6c9-05b8-4297-aae6-2b7af7320d67/files/solo-staging-auth-dev`.
It is a review artifact, not a released or approved package. Its manifest
records a 35-entry execution manifest and 28 migration files. The candidate
target is `0027_storage_lifecycle`; `0028_storage_cleanup_leases` is included
as provenance and must remain unapplied.

The current checkout's 26-file `staging_guard.py` is incompatible with this
artifact and must not be used. The frozen artifact was not changed; its archive
SHA-256 remains
`58da2d95be04aa7077c8c5b0b76965fcbb7f99f86b210b5565d5e94285e1108d`,
its execution-manifest SHA-256 remains
`1bd5ba5867b5a3bef7efe6413df0c21dd0d2fa5260180705322013ad7f4f8eaf`, and its
guard SHA-256 remains
`47a26dc315085537579b4abee2f642ec7bd5b1513feb6ebf900be5ab047b8155`.
Those hashes describe the frozen artifact, not the new development artifact.

The non-frozen staging documentation was updated to make the earlier
26-revision review historical and to use the 28-file/0027 candidate for this
preflight. Frozen documents and manifests remain unchanged.

## Solo-maintainer authorization

The adopted policy permits the owner to authorize one non-production
operation at a time unless a contract, law, or provider rule requires
independence. The authorization is self-attributed evidence, not an
independent signature. Each record must bind:

- `operation: preflight`, a unique authorization ID, owner identity, reason,
  UTC approval/expiry times with no more than 24 hours between them;
- exact resource ID, external hostname, port, database, and PostgreSQL major;
- reviewed archive and execution-manifest paths and SHA-256 values;
- approved CA path and SHA-256; and
- the result in a sanitized audit log outside the artifact.

For the first preflight, use `verify-full` and the approved system CA. The new
guard rejects the legacy TLS downgrade exception. Do not put credentials or
full connection URLs in the authorization record or audit log. The owner
identity in the record must match `STAGING_OWNER_ID`; this is attribution, not
authentication. A preflight authorization permits only the guarded read-only
catalog inspection; migration, postflight, deployment, and OAuth activation
require separate decisions.

## Role contract to verify

The preflight connects only as `vervfy_oauth_staging_user`. It requires the
expected database/session identity, PostgreSQL 18, verified TLS, and the
reviewed role graph. It does not authenticate using the application logins.
The three staging-only URLs are still required by local `check` and must be
loaded from the staging secret store:

- `MIGRATION_DATABASE_URL`: `vervfy_oauth_staging_user`;
- `DATABASE_URL`: `app_runtime`; and
- `GOOGLE_IDENTITY_LOOKUP_DATABASE_URL`: `google_auth_lookup`.

The read-only SQL verifies that runtime roles have no superuser,
`BYPASSRLS`, database/schema creation, or unsafe membership; that
`google_auth_lookup` alone inherits the restricted identity lookup executor
without `SET` or `ADMIN`; and that the migration login can perform the
reviewed schema work without superuser or `BYPASSRLS`. It also reports
effective memberships, object/default ACLs, owners, database settings, and
the restricted storage capability graph required by 0027. These are source
expectations only: actual hosted role attributes, grants, default ACLs, and
password validity remain unverified until the authorized preflight output is
reviewed. A passing assertion is not a substitute for reviewing every report.

## Local check and first hosted operation

The correct local guard is
`~/.copilot/session-state/c71be6c9-05b8-4297-aae6-2b7af7320d67/files/solo-staging-auth-dev/source/staging_guard.py`,
not the checkout guard or the frozen guard. `check` opens no connection, but
still requires the complete operation-specific approval, artifact/manifest
hashes, CA file, and all three staging URLs. No such approval or URLs are
currently recorded here, so no successful `check` is claimed.

After the owner prepares the preflight authorization and loads staging URLs
privately, run `staging_guard.py check` from that exact development artifact.
Only after local `check` passes and the owner explicitly authorizes the hosted
operation may `staging_guard.py preflight` run. It uses
`docs/staging-alembic-preflight.sql` in `BEGIN READ ONLY` and ends with
`ROLLBACK`; it does not authorize or perform a migration. Migration target
0027 requires a later, separate owner decision and tested recovery. Production
OAuth activation is a separate later decision and remains disabled.
