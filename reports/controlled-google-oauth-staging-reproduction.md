# Controlled Google OAuth staging reproduction — 2026-11-08

Overall: BLOCKED. The actual staging environment has not been supplied to the agent. No authentication attempt was made; the historical callback HTTP 503 cause remains unconfirmed.

## Evidence

- CONFIRMED: detached HEAD at dd22f18 (no current branch). Initial inventory contains 64 modified tracked files plus untracked files/directories. Full initial status is appended below. Existing changes preserved; no implementation or environment files edited.
- CONFIRMED: /home/sam/vervfy-local-staging/venv312/bin/python reports Python 3.12.7.
- CONFIRMED: local PostgreSQL listens on 127.0.0.1:55432, PID 3850, with process cwd /home/sam/vervfy-local-staging/postgres-data. TCP connection succeeds.
- BLOCKED: PostgreSQL authenticated connectivity, intended database identity, runtime role permissions and restricted identity lookup execution require approved staging connection configuration. TCP connectivity alone does not establish these.
- CONFIRMED: PID 5669 uses /usr/bin/valkey-server, listens on 127.0.0.1:6379, responds to PING, and reports noeviction. No keys or application data read. Its match to the intended application REDIS_URL is unverified.
- CONFIRMED: existing Next.js PID 8476 runs from this checkout's web directory on 127.0.0.1:3000. Its actual process BACKEND_URL matches the requested loopback FastAPI endpoint. GET / and /register return 200; GET /api/config returns 500.
- CONFIRMED: 127.0.0.1:8000 refuses connections. No FastAPI listener exists. No duplicate services started.
- CONFIRMED: Google public OIDC discovery returns 200 under Python 3.12.7; issuer, token endpoint and JWKS URI match source expectations. This does not verify application OAuth initialization, JWKS fetching, token exchange or token validation.
- BLOCKED: no active Cloudflare process/hostname verified. cloudflared is installed. No tunnel started while application configuration is missing. Existing allowedDevOrigins contains an old Quick Tunnel hostname and must be compared with a newly issued hostname.
- BLOCKED: Google Console client isolation, authorized origins, redirect URIs and test-account authorization unverified. No Google Cloud settings changed.
- CONFIRMED: production render.yaml declares GOOGLE_OAUTH_ENABLED disabled. Production was not contacted or modified; deployed production state was not independently queried.

## Environment presence (values withheld)

Agent environment: REDIS_URL is present, but its intended staging provenance is unverified. All other requested variables are absent: GOOGLE_OAUTH_ENABLED, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, GOOGLE_FRONTEND_ORIGIN, GOOGLE_IDENTITY_LOOKUP_DATABASE_URL, DATABASE_URL, BACKEND_URL, VERVFY_ENVIRONMENT, VERVFY_HTTPS_ONLY, VERVFY_COOKIE_SAME_SITE.

Next.js process: BACKEND_URL is present and matches the intended local API. The other requested variables are absent from its inherited process environment; backend secrets need not be supplied to Next.js.

Only .env.example files were found in the inspected repository/root/web/staging locations. No actual staging env file was found there. No other terminal environment was imported. FastAPI cannot yet be launched with a verified intended environment.

## OAuth preflight and callback

BLOCKED: FastAPI health/configuration, service initialization, restricted identity lookup, actual browser cookie attributes, HTTPS callback, and successful frontend API routing.

Source sets HttpOnly, Secure for HTTPS, SameSite=Lax browser-binding cookies at server.py:1528. Actual runtime cookie configuration remains unverified. Callback path must be /api/auth/google/callback on the fresh HTTPS frontend origin.

NOT REPRODUCED: no controlled Google callback was attempted because required preflight gates did not pass. This status is not evidence of successful authentication. Signup and linked-account login remain unverified.

Existing diagnostics: server.py:1787 transaction consumption backend failure; :1805 provider failure during exchange/validation; :1811 backend failure during exchange/validation; :1934 downstream failures. Downstream catch covers identity lookup (:1819), pending signup (:1821), user retrieval and session creation (:1834 onward). Category-only logs may not identify the exact downstream operation. google_oauth.py:534 implements exchange/validation; :631 identity lookup; :657 pending signup. provider_identity_lookup.py:28 executes the restricted function. No speculative fixes or diagnostic code changes made.

## Next action

Provide the local path to the approved staging environment file or launcher, without pasting secrets. Validate connection targets and configuration before loading it into a dedicated FastAPI process. Verify authenticated database identity and permissions without reading user data or changing grants. Then prepare a fresh tunnel to Next.js, compare all origins/callbacks, obtain authorization for required Google Console changes, and have the authorized test-account owner authenticate during the controlled attempt. Correlate sanitized operation-level evidence before attributing the 503.

REQUIRES HOSTED VERIFICATION: local tunnel success would not establish hosted proxy/provider behavior. Production enablement remains outside this task.

No migrations, grants, credential invention, account-data access, production connections, commits, resets, stashes or pushes performed. No service started or stopped.

## Initial modification inventory

```text
 M .env.example
 M alembic/env.py
 M alembic/versions/0001_postgres_persistence.py
 M alembic/versions/0002_profile_photo.py
 M alembic/versions/0003_track_size.py
 M alembic/versions/0004_session_version.py
 M alembic/versions/0005_storage_path.py
 M alembic/versions/0006_tenant_integrity.py
 M alembic/versions/0007_row_level_security.py
 M alembic/versions/0008_upload_jobs.py
 M alembic/versions/0009_upload_retry_count.py
 M alembic/versions/0010_verified_account_email.py
 M alembic/versions/0011_playlist_position.py
 M alembic/versions/0012_artist_image_cache.py
 M alembic/versions/0013_artist_catalog.py
 M alembic/versions/0014_user_covers_remove_artist_catalog.py
 M alembic/versions/0015_artist_photos.py
 M alembic/versions/0016_audiodb_artist_images.py
 M alembic/versions/0017_track_covers.py
 M alembic/versions/0018_cover_checked_at.py
 M alembic/versions/0019_track_listens.py
 M alembic/versions/0020_playlist_last_played.py
 M artist_images.py
 M audio_store.py
 M auth.py
 M cover_art.py
 M database.py
 M db.py
 M docs/third-party-data.md
 M library.py
 M migrate.py
 M render.yaml
 M requirements.txt
 M scripts/backfill_cover_storage.py
 M scripts/backfill_covers.py
 M scripts/migrate_audio_to_storage.py
 M scripts/migrate_local_data.py
 M scripts/move_audio_to_storage.py
 M scripts/rebuild_covers.py
 M scripts/upload_worker.py
 M server.py
 M tests/test_album_covers.py
 M tests/test_artist_images.py
 M tests/test_artist_photos.py
 M tests/test_artist_profiles.py
 M tests/test_audio_store_streaming.py
 M tests/test_audio_stream_redirect.py
 M tests/test_cover_art.py
 M tests/test_provider_regression_guard.py
 M tests/test_rebuild_covers.py
 M tests/test_security_regressions.py
 M tests/test_track_covers.py
 M tests/test_track_listens.py
 M tests/test_upload_metadata.py
 M upload_queue.py
 M web/next.config.ts
 M web/src/app/auth.css
 M web/src/components/account-settings.tsx
 M web/src/components/auth/auth-form.tsx
 M web/src/components/library-app.tsx
 M web/src/lib/api/types.ts
 M web/src/lib/i18n.tsx
 M web/src/lib/lrclib-proxy.ts
 M web/test-results/.last-run.json
?? alembic/versions/0021_provider_identities.py
?? alembic/versions/0022_provider_identity_lookup.py
?? alembic/versions/0023_missing_media_columns.py
?? alembic/versions/0024_provider_identity_runtime_access.py
?? alembic/versions/0025_track_cover_sources.py
?? alembic/versions/0026_application_runtime_grants.py
?? alembic/versions/0027_storage_lifecycle.py
?? alembic/versions/0028_storage_cleanup_leases.py
?? alembic/versions/0029_storage_cleanup_retry_limits.py
?? alembic/versions/0030_operator_foundation.py
?? alembic/versions/0031_operator_revocation_bootstrap_guards.py
?? docs/account-deletion-production-checklist.md
?? docs/google-oauth-readiness.md
?? docs/google-oauth-staging-runbook.md
?? docs/render-staging-proposal.md
?? docs/security-readiness-audit.md
?? docs/staging-alembic-postflight.sql
?? docs/staging-alembic-preflight.sql
?? docs/staging-alembic-review.md
?? docs/staging-db-bootstrap-proposal.sql
?? docs/staging-db-initialization-runbook.md
?? docs/staging-db-metadata-postflight.sql
?? docs/staging-db-metadata-preflight.sql
?? docs/staging-endpoint-approval.md
?? docs/staging-recreation-recovery.md
?? docs/storage-lifecycle.md
?? docs/storage-namespace-initialization.md
?? google_oauth.py
?? provider_identity_lookup.py
?? render.staging.proposal.yaml
?? reports/
?? request_limits.py
?? requirements.lock
?? ruff.toml
?? scripts/storage_cleanup_worker.py
?? staging_guard.py
?? staging_metadata_preflight.py
?? storage_adapters.py
?? storage_lifecycle.py
?? storage_namespace.py
?? tests/readiness_backend.py
?? tests/storage_lifecycle_fixture.py
?? tests/test_account_password_throttle.py
?? tests/test_filesystem_storage.py
?? tests/test_google_oauth.py
?? tests/test_google_oauth_redis_integration.py
?? tests/test_oauth_postgres.py
?? tests/test_oauth_schema.py
?? tests/test_operator_identity_foundation.py
?? tests/test_queued_artwork.py
?? tests/test_readiness_security.py
?? tests/test_release_postgres.py
?? tests/test_staging_guard.py
?? tests/test_staging_metadata_preflight.py
?? tests/test_staging_migrations.py
?? tests/test_staging_render_config.py
?? tests/test_storage_boundaries.py
?? tests/test_storage_cleanup.py
?? tests/test_storage_lifecycle.py
?? tests/test_storage_writers.py
```

## Follow-up: user-identified frontend environment file

Inspected variable names only in /home/sam/vervfy-latest/web/.env.local. The sole defined name is BACKEND_URL. Values were not evaluated, loaded into any process, copied, or printed. The file was not modified. This file is outside the active phase4a-retry-limits/web checkout; no assumption was made that the running frontend loads it.

Missing names: GOOGLE_OAUTH_ENABLED, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, GOOGLE_FRONTEND_ORIGIN, DATABASE_URL, GOOGLE_IDENTITY_LOOKUP_DATABASE_URL, REDIS_URL, VERVFY_ENVIRONMENT, VERVFY_HTTPS_ONLY, VERVFY_COOKIE_SAME_SITE.

BLOCKED: this frontend file does not supply the backend staging configuration. Previously confirmed local TCP/PING/HTTP evidence remains insufficient to establish authenticated database identity or restricted lookup privileges. No credentials were invented or sourced from production.

## Configuration discovery and offline review follow-up

### Discovery scope and result

CONFIRMED: /home/sam/.config/vervfy/staging.env exists, mode 0600, and defines only DATABASE_URL. Only variable names and filesystem metadata were inspected. Its value, destination, validity, and approval status remain unverified. This supersedes the earlier limited search result; it does not establish a complete approved backend configuration.

Inspected shell configuration variable names in .bashrc and .bash_profile; no backend staging names or recognized environment-manager integration found. Inspected candidate filenames under ~/.config/vervfy, ~/.config/systemd/user, ~/.config/direnv, ~/.config/mise, ~/.local/bin, the local staging directory, repository trees and the prior security-remediation tree. Excluded history, production-named files/directories, credential stores, data directories and dependency trees. No complete local launcher surfaced. The scan encountered a Unix socket, stopped, then continued with a narrower regular-file scan; no socket content was read.

secret-tool is installed; direnv, mise, op, doppler, infisical and pass were not found on this agent's PATH. Installation is not evidence of an approved Vervfy secret-store entry. No secret-store entries were queried. No exhaustive claim is made about encrypted stores, other shells, or files outside this search scope.

Documented procedures exist in docs/google-oauth-staging-runbook.md, docs/staging-db-initialization-runbook.md, docs/staging-recreation-recovery.md and docs/storage-namespace-initialization.md. These are setup/review procedures, not populated local launchers. Historical role SQL is explicitly superseded; hosted bootstrap and migration instructions do not authorize running them now.

### Required configuration and provenance

| Variable | Required origin / handling |
|---|---|
| GOOGLE_CLIENT_ID | Existing approved staging-only Google Web OAuth client in the owner's Google Cloud project. Never fabricate or copy production's client. |
| GOOGLE_CLIENT_SECRET | Secret for that same staging client, supplied by the owner's approved secret storage. Do not generate an arbitrary substitute or rotate without authorization. |
| DATABASE_URL | Existing local staging database, ordinary runtime role and actual authentication settings. A candidate exists in ~/.config/vervfy/staging.env but must be verified without disclosure before use. Never substitute the owner or migration login. |
| GOOGLE_IDENTITY_LOOKUP_DATABASE_URL | Same verified isolated database, dedicated restricted lookup login and existing authentication settings. Must prove actual privileges; a different username alone is insufficient. |
| REDIS_URL | Existing isolated Valkey endpoint, database selection and authentication/TLS settings if configured. Local PING does not establish the correct logical database or approved authentication configuration. |
| VERVFY_SECRET_KEY | Recover the existing staging-only session signing secret if available. Otherwise generate a cryptographically random staging-only secret directly into approved private storage; never display it. A replacement invalidates existing staging sessions. |
| GOOGLE_OAUTH_ENABLED | Explicit staging policy setting: disabled during initial configuration; enable only in the isolated backend once dependencies/configuration and origin registration are verified. Production remains disabled. |
| GOOGLE_FRONTEND_ORIGIN | Fresh, verified HTTPS Quick Tunnel origin generated for this test window. Not a historical hostname. |
| GOOGLE_REDIRECT_URI | Derive from the exact fresh origin plus /api/auth/google/callback. Register that exact URI in the approved staging Google client after required authorization. |
| BACKEND_URL | Frontend-only routing configuration for http://127.0.0.1:8000. Already confirmed in the active frontend process; do not assume the other checkout's env file is loaded. |
| VERVFY_ENVIRONMENT | Explicit staging mode for this existing cluster. Do not select local-test casually: it activates additional filesystem/disposable-cluster restrictions described below. |
| VERVFY_HTTPS_ONLY | Explicit enabled setting for the HTTPS browser test, to secure session cookies. |
| VERVFY_COOKIE_SAME_SITE | Explicit lax setting, required by OAuth initialization. |
| VERVFY_TRUSTED_PROXY_HOPS | Derive from observed Cloudflare → Next → FastAPI forwarded-header handling and trusted local proxy topology. Do not copy a hosted example's count. |

The discovered backend candidate is missing every table entry except DATABASE_URL. The separate frontend file defines BACKEND_URL only. No complete intended backend environment is established by combining these findings.

Generated values: a new tunnel hostname, its derived callback URI, and only if needed a new staging session-signing secret. Google issues the client credentials; existing infrastructure supplies the database/lookup/Valkey settings. No database role passwords, grants or resources should be invented or changed to fill gaps.

Conditional storage variables are not prerequisites merely because OAuth is being tested. Keep SUPABASE_URL, SUPABASE_SERVICE_KEY and SUPABASE_BUCKET absent from an OAuth-only local launch unless an approved isolated storage configuration is explicitly needed. Configuring remote storage activates private-bucket/namespace checks and may make external calls. Media testing additionally needs the existing approved storage namespace binding (VERVFY_STORAGE_NAMESPACE_ID), backend choice and storage settings. Do not create a namespace, grant or migration as part of configuration recovery. Keep migration/admin credentials out of the API environment.

### Secure setup procedure (not executed)

1. Establish provenance of the discovered staging.env with the local staging owner. Review only sanitized destination predicates and role/database metadata before allowing a connection; do not source it blindly as shell code. Confirm no production destination, broad role or inherited PG* override. The current names-only authorization does not validate its value.
2. Recover missing entries from the approved staging secret source. Use hidden interactive input or an existing approved secret-manager injection path, never shell command arguments, history, pasted chat, terminal echo, debug tracing or NEXT_PUBLIC_* variables. Do not overwrite the existing partial env file. If a new private store is later authorized, use owner-only directory/file permissions and populate only real verified values; no placeholder credentials. No such store was created here.
3. Build a minimal allowlisted child environment for the backend and launch from the intended checkout with the absolute Python 3.12.7 interpreter. Do not inherit unrelated production/cloud/storage variables. Check required-name presence, semantic predicates and approved local targets in that same child before importing the application. Report booleans and exception categories only, never environment dumps or raw connection errors.
4. Using verified runtime and lookup connections, perform read-only database identity, role, function-execution privilege, RLS and schema metadata checks. Verify restricted lookup with a synthetic, non-user subject and suppress returned identifiers. Do not query real accounts, migrate, change grants or bypass lookup. Verify the intended Valkey client with PING before testing isolated single-use transaction semantics.
5. Check existing listeners before each launch. Start FastAPI only on 127.0.0.1:8000 using uvicorn with --no-access-log, so callback query strings are not printed. Inspect frontend/tunnel logging for the same exclusion; no HTTP wire/debug logs. Keep application error reporting limited to sanitized operation/exception categories. Confirm the actual backend child environment and health/config responses. Reuse the existing local Next process where its loaded configuration is correct.
6. Once the local app is healthy, start the authorized Quick Tunnel to http://127.0.0.1:3000, capture its hostname, and compare it against the frontend origin, callback URI and allowedDevOrigins. Preserve existing Next configuration edits when updating the allowlist. Obtain authorization before changing Google Cloud registrations; a local configuration change cannot establish Google Console registration.
7. Restart only the affected local app processes with the verified matching configuration, HTTPS-only session cookies and SameSite=Lax. Verify Google service initialization, public metadata/JWKS retrieval, API rewrites, browser cookie attributes and exact callback. Do not follow an authentication flow until all gates pass and an authorized test account is available.
8. Conduct the controlled signup attempt with the account owner, recording only request timing, status, operation and exception category. Signup success alone does not establish linked-account login. Verify both separately before declaring OAuth operational; stop the temporary tunnel after the test window.

### Independently actionable offline findings

- CONFIRMED — Backend imports require DATABASE_URL immediately (db.py:53). No dotenv loader exists in the inspected server.py/db.py/google_oauth.py modules. Merely finding a file does not supply the API process environment. Explicit injection is required.
- CONFIRMED — Startup checks required schema columns and storage-reference triggers (server.py:1362), but does not establish restricted OAuth lookup-function privileges. Successful application startup or /api/config is insufficient OAuth readiness evidence. Use the read-only lookup preflight independently; do not infer a migration is needed.
- CONFIRMED — OAuth service construction creates lazy engine/Redis clients (google_oauth.py:375). Initialization success is not proof of dependency connectivity or permissions.
- CONFIRMED — The callback provider category combines token exchange, metadata and signing-key retrieval failures (google_oauth.py:534; server.py:1805). The downstream category combines identity lookup, pending-signup Redis storage, user retrieval and session creation (server.py:1818–1939). Existing class-only logs cannot always identify an exact operation. Before the controlled attempt, prepare a reviewed non-payload diagnostic mechanism that records operation and exception class only; do not enable raw stack/local-variable/HTTP payload logging. No instrumentation change was made in this task.
- CONFIRMED — Filesystem test mode is incompatible with the observed cluster location as currently defined: storage_adapters.py:49 requires a passwordless Unix-socket database named postgres under /tmp/vervfy-storage-pg-*, with specified runtime/lookup roles; :80 requires local-test plus filesystem and rejects Supabase/PG* settings. The observed cluster is under /home/sam/vervfy-local-staging. This is an independent configuration constraint, not evidence for the historical OAuth 503. Do not weaken it or move/recreate the database implicitly.
- CONFIRMED — Next allowedDevOrigins contains a historical Quick Tunnel hostname (web/next.config.ts:17). It needs comparison/update after a fresh hostname is issued, preserving the existing diff. This setting does not register the callback with Google.
- CONFIRMED — Session signing otherwise falls back to a local file/generated key (server.py:95). Explicit staging secret provenance prevents accidental reuse or silent new session identity during reproduction.

Overall BLOCKED; historical callback failure NOT REPRODUCED. No configuration values were displayed, no production credentials/history were inspected, no credentials requested or created, no authentication attempted, and no implementation or environment files modified. Only this investigation report was extended. Hosted behavior still REQUIRES HOSTED VERIFICATION.
