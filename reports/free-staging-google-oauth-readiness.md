# Vervfy Phase 2.3 — Free Staging & Live Google OAuth Readiness

**Assessment date:** 2026-11-07
**Decision:** Local first-login preparation is ready; the real Google test is
**not yet authorized or performed**. Google OAuth remains disabled. No hosted
resource was accessed, started, created, or deployed; no tunnel was started;
no credentials were added; and no hosted or staging migration was run by this
task. The PostgreSQL test exercised only isolated, synthetic migrations
0021–0024 as part of its test fixture.

## Scope and worktree preservation

Reviewed:

- `reports/google-oauth-production-release-gate.md`
- `reports/staging-configuration-remediation.md`
- `reports/final-staging-preflight.md`
- `docs/google-oauth-readiness.md`
- `docs/google-oauth-staging-runbook.md`
- `docs/render-staging-proposal.md`
- `render.staging.proposal.yaml`
- `google_oauth.py`, `server.py`, `web/next.config.ts`, and the focused OAuth,
  PostgreSQL, Redis, and Render-configuration tests.

The worktree was already extensively dirty at `dd22f18` and contains existing
tracked changes and untracked files, including migrations 0028–0031. They were
preserved. The only repository file added for this task is this report.
Migrations 0028–0031 were neither changed nor executed. The OAuth/PostgreSQL
test below exercises only the isolated 0021–0024 test migrations.

There is a hosted-state evidence conflict that must not be resolved by
guessing: an earlier user-provided dashboard observation reported Render
PostgreSQL resource `dpg-dbl7q66tlv9c73b883jg-a` as available, database
`vervfy_oauth_staging`, PostgreSQL 18, with default user
`vervfy_oauth_staging_user`; an earlier report says no hosted resource had been
created, while the staging proposal expects a separate bootstrap login.
Render Support was also reported to confirm external PostgreSQL
`sslmode=verify-full` with the standard system CA. None of those hosted facts
was independently rechecked here. In particular, the reported database user
does not match the proposal's bootstrap identity. Do not connect, migrate, or
reuse that resource until its identity, role graph, isolation, and current
state are revalidated under separate approval.

## $0 local topology

The recommended first live test is a temporary local stack, not a Render
deployment:

```text
Google browser
    │ HTTPS (temporary Cloudflare Quick Tunnel)
    ▼
Next.js 127.0.0.1:3000 ── same-origin /api rewrite ──► FastAPI 127.0.0.1:8000
                                                           │
                         private Unix socket ┌─────────────┴──────────────┐
                         PostgreSQL 18        │       local Valkey         │
```

Google's callback lands on the public Next.js tunnel host and Next's existing
`/api/:path*` rewrite sends it to the local FastAPI callback. PostgreSQL and
Valkey remain on loopback/private Unix sockets; the API and frontend bind to
loopback. No Supabase, production data, Storage credentials, production
services, or production secrets are needed for auth-only testing. The
temporary tunnel is nevertheless public to anyone who obtains its URL; it is
not an access-control boundary.

Local prerequisites were present: Python 3.12.7, PostgreSQL 18.6,
`valkey-server`, `redis-server`, Node/npm, the installed Next CLI under
`web/node_modules`, and `cloudflared`. None of these services was started for
this assessment.

### Operator sequence — local disposable database and services

These are instructions for a later, separately authorized test window; they
were not run. Use a non-root OS account. Keep the whole cluster in a newly
created temporary directory, never in the repository or an existing database.

1. Prepare locked Python dependencies and frontend packages if not already
   installed:

   ```sh
   export OAUTH_TMP="$(mktemp -d /tmp/vervfy-oauth-local.XXXXXX)"
   chmod 700 "$OAUTH_TMP"
   uv venv --python 3.12.7 "$OAUTH_TMP/venv"
   uv pip install --python "$OAUTH_TMP/venv/bin/python" \
     --require-hashes -r requirements.lock
   (cd web && npm ci)
   ```

2. Initialize PostgreSQL 18 in that directory. `trust` is restricted to the
   private Unix socket here: the socket directory is mode 0700 and TCP
   listening is disabled. Do not copy this authentication mode to a hosted
   database.

   ```sh
   initdb -D "$OAUTH_TMP/pgdata" \
     --auth-local=trust --auth-host=reject \
     --username=local_admin --no-locale --encoding=UTF8
   pg_ctl -D "$OAUTH_TMP/pgdata" \
     -l "$OAUTH_TMP/postgres.log" \
     -o "-k $OAUTH_TMP -c listen_addresses='' -c unix_socket_permissions=0700" \
     -w start
   createdb -h "$OAUTH_TMP" -U local_admin \
     --owner=local_admin vervfy_oauth_local
   psql -h "$OAUTH_TMP" -U local_admin -d vervfy_oauth_local \
     -v staging_db=vervfy_oauth_local \
     -f docs/staging-db-bootstrap-proposal.sql
   ```

   The reviewed bootstrap proposal creates the restricted local role graph.
   This use is only for the fresh, private disposable cluster; it is not
   authorization to execute the SQL or any database command on Render.

3. In a separate terminal, run Valkey on a private Unix socket with persistence
   disabled for the throwaway test:

   ```sh
   valkey-server --port 0 \
     --unixsocket "$OAUTH_TMP/valkey.sock" --unixsocketperm 700 \
     --save "" --appendonly no --protected-mode yes \
     --daemonize no --dir "$OAUTH_TMP"
   ```

   Keep this process alive during browser testing. A restart intentionally
   drops local sessions and OAuth state.

4. Apply only the reviewed release boundary to the fresh local database. Use
   these values in the migration terminal (the socket host keeps connections
   local); do not use `head` or any revision after 0027:

   ```sh
   export VERVFY_ENVIRONMENT=development
   export DATABASE_URL="postgresql+psycopg://app_runtime@/vervfy_oauth_local?host=$OAUTH_TMP"
   export MIGRATION_DATABASE_URL="postgresql+psycopg://vervfy_oauth_staging_user@/vervfy_oauth_local?host=$OAUTH_TMP"
   "$OAUTH_TMP/venv/bin/python" -m alembic upgrade 0027_storage_lifecycle
   "$OAUTH_TMP/venv/bin/python" -m alembic current
   ```

   Continue only if the resulting revision is exactly
   `0027_storage_lifecycle`. This is a local disposable-database operation;
   hosted migrations remain blocked behind the existing hash-bound guard,
   DBA/release approval, and recovery requirements. Do not execute 0028–0031.

5. Start the API with OAuth still disabled. In its own terminal, set:

   ```sh
   export VERVFY_ENVIRONMENT=development
   export VERVFY_HTTPS_ONLY=1
   export VERVFY_COOKIE_SAME_SITE=lax
   export VERVFY_SECRET_KEY="$("$OAUTH_TMP/venv/bin/python" -c 'import secrets; print(secrets.token_urlsafe(48))')"
   export DATABASE_URL="postgresql+psycopg://app_runtime@/vervfy_oauth_local?host=$OAUTH_TMP"
   export REDIS_URL="unix://$OAUTH_TMP/valkey.sock?db=0"
   export GOOGLE_OAUTH_ENABLED=0
   unset GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET GOOGLE_REDIRECT_URI \
     GOOGLE_FRONTEND_ORIGIN GOOGLE_IDENTITY_LOOKUP_DATABASE_URL
   "$OAUTH_TMP/venv/bin/python" -m uvicorn server:app \
     --host 127.0.0.1 --port 8000 --no-access-log --lifespan on
   ```

   Do not place the migration URL in the API environment. Verify the API
   reaches only this local PostgreSQL/Valkey and reports Google disabled.

6. In another terminal, start Next.js on loopback. `BACKEND_URL` is the local
   FastAPI origin; browser requests remain same-origin through the rewrite:

   ```sh
   cd web
   BACKEND_URL=http://127.0.0.1:8000 \
     npm run dev -- --hostname 127.0.0.1 --port 3000
   ```

7. Only after the tunnel authorization below, start the temporary HTTPS
   forwarder in a separate terminal:

   ```sh
   cloudflared tunnel --url http://127.0.0.1:3000
   ```

   Record the generated `https://<unique-host>.trycloudflare.com` origin in
   the operator's private notes, not in source control. Keep the tunnel
   running only for the approved test. If its hostname changes, stop and
   re-register/reconfigure the exact callback before another OAuth attempt.

### Google testing client and exact callback

Use an approved, distinct Google Cloud project and **Web application** OAuth
client for testing, never a production client. The callback value is the
actual tunnel origin plus this exact path:

```text
GOOGLE_FRONTEND_ORIGIN=https://<actual-tunnel-host>
GOOGLE_REDIRECT_URI=https://<actual-tunnel-host>/api/auth/google/callback
```

Register that full redirect URI byte-for-byte in Google Cloud's authorized
redirect URIs. Do not register the API origin, localhost alternative,
wildcards, trailing-slash variant, or another path. Add only the exact
`https://<actual-tunnel-host>` authorized JavaScript origin if the client
configuration specifically requires one. The implementation uses
`CALLBACK_PATH = "/api/auth/google/callback"` and rejects a callback whose
scheme/host or path differs from the configured frontend origin. The Next.js
rewrite routes `/api/*` to FastAPI.

Current code requests only `openid email profile`, uses Authorization Code
with S256 PKCE, and validates Google OIDC state, nonce, issuer, audience,
signature, and time claims. It does not need Gmail/Drive scopes or unrelated
Google APIs. For sensitive account actions it requests `max_age=300` and
essential `auth_time`; that is not part of ordinary first sign-in.

Google's current audience guidance says **External / Testing** projects permit
up to 100 listed test users; use one dedicated, controlled Google test account
for this test. **Important nuance:** Google's published exception for apps
requesting only name/email/profile (`openid email profile`) says users need
not be on the test-user list and those grants do not expire after seven days.
Therefore do not treat the Testing test-user list as an access-control boundary
for this sign-in-only scope set. Keep the tunnel URL private, use no customer
or production account/data, and stop the public tunnel promptly. If the Google
console rejects a `trycloudflare.com` host under its redirect/domain checks,
stop; do not work around it with a wildcard or broad domain. A verified,
owner-controlled HTTPS hostname would then need separate approval.

After all approvals and client registration, restart the API with these
API-only values set in its process environment:

```text
GOOGLE_OAUTH_ENABLED=1
GOOGLE_CLIENT_ID=<test Web client ID>
GOOGLE_CLIENT_SECRET=<read from the approved secret store / hidden prompt>
GOOGLE_FRONTEND_ORIGIN=https://<actual-tunnel-host>
GOOGLE_REDIRECT_URI=https://<actual-tunnel-host>/api/auth/google/callback
GOOGLE_IDENTITY_LOOKUP_DATABASE_URL=postgresql+psycopg://google_auth_lookup@/vervfy_oauth_local?host=<OAUTH_TMP>
```

Keep the Google client secret out of the frontend, `NEXT_PUBLIC_*`, shell
history, repository files, logs, and reports. The lookup URL must use the
separate `google_auth_lookup` principal; `DATABASE_URL` remains
`app_runtime`. Keep `GOOGLE_OAUTH_ENABLED=0` until the last pre-enable check,
then restart only the local API after the operator explicitly authorizes this
local test. The app reads this configuration at process startup.

### First real browser test

1. Verify the public tunnel serves the local Vervfy frontend and `/api/config`
   reports Google disabled before the client secret is entered. Confirm
   PostgreSQL is at 0027, Valkey is reachable, and no Storage/production
   variables are configured.
2. After the Google Cloud client and local enablement are separately
   authorized, open the Vervfy sign-up view and choose **Continue with Google**.
   Use the dedicated test Google account. The first unlinked identity must use
   `purpose=signup`; a login attempt for an unlinked identity is intentionally
   rejected and email similarity must not auto-link accounts.
3. Complete Google authentication and choose a synthetic, unique Vervfy
   username during onboarding. Verify one new local account and a fresh Vervfy
   session; do not copy authorization codes, state, nonce, cookies, tokens, or
   personal profile data into evidence.
4. Log out, return to the sign-in view, and complete Google login for that now
   linked test identity. Verify the callback returns through the public
   frontend origin and that the browser-binding/session cookies are Secure,
   HttpOnly, SameSite=Lax, and not exposed to JavaScript. Review only sanitized
   logs; Uvicorn access logging is disabled to avoid logging callback query
   strings.
5. Stop on any callback mismatch, cookie/proxy issue, provider error, unexpected
   account linking, Redis/DB error, or sensitive log output. Set local
   `GOOGLE_OAUTH_ENABLED=0`, stop the tunnel and application processes, then
   stop PostgreSQL with
   `pg_ctl -D "$OAUTH_TMP/pgdata" -m fast -w stop`. Remove only the exact
   temporary directory created for this run after confirming it contains no
   needed evidence.

This is a first-login smoke test, not production or hosted-staging sign-off.
It does not prove Render proxy behavior, managed PostgreSQL permissions,
backups, hosted Valkey behavior, or production controls.

## Free Render option — evaluated separately

`render.staging.proposal.yaml` describes separate Free PostgreSQL, Key Value
(Valkey), FastAPI, and Next.js resources and keeps OAuth off. It is not the
production `render.yaml`; do not apply either file as part of this task.
Potentially `$0` hosted use depends on currently available workspace slots,
usage limits, and dashboard billing terms. A prior user-provided dashboard
snapshot suggests a staging PostgreSQL resource already exists, so do not
assume another Free database slot is available.

Render's current free-plan documentation states:

- Free web services sleep after 15 minutes idle and take about a minute to
  wake. Their 750 free instance hours are shared per workspace/month; bandwidth
  and build limits can suspend services or incur supplementary charges based
  on billing configuration.
- Only one Free PostgreSQL and one Free Key Value can be active per workspace.
  Free PostgreSQL is 1 GB, expires after 30 days (with a 14-day upgrade grace
  period before deletion), and has no backups.
- Free Key Value is in-memory only. A restart loses all data; maintenance and
  provider restarts are possible. It must **not** be treated as durable
  persistence for Vervfy's session allowlist, user-session index, rate limits,
  OAuth transaction state, or reauthentication proofs. Lost OAuth state must
  fail closed; lost sessions require sign-in again.

`noeviction` prevents silent key eviction when configured but does not make
Free Valkey persistent or prevent restart/outage loss. This can be acceptable
for a short synthetic browser experiment if interruptions are expected; it is
not a durable-session solution or production architecture. If hosted parity is
later required, separately approve the exact resources, role bootstrap,
metadata preflight, migration target/backup plan, secrets, and Render preview.
Do not use the historical `render.yaml` production resources or connect the
local API to the reported hosted database.

## Focused local validation

Dependencies were installed from `requirements.lock` into a temporary Python
3.12.7 environment outside the repository. Tests used synthetic data and
disposable local backends only:

| Check | Result |
|---|---:|
| `tests/test_google_oauth.py` | **23 passed** with `DATABASE_URL=sqlite://`, OAuth explicitly disabled in the test process, and no provider calls. Covers mocked token, state/replay, cookie, onboarding, link, and fail-closed cases. |
| `tests/test_google_oauth_redis_integration.py` | **4 passed** with a disposable local Redis Unix socket: atomic consume/replay, TTL, missing state, and outage. |
| `tests/test_oauth_postgres.py` | **21 passed** using a private disposable PostgreSQL 18.6 Unix-socket cluster; exercises only migrations 0021–0024 and synthetic role/RLS cases. |
| `tests/test_staging_render_config.py` | **3 passed** for the separate proposal's resource isolation, references, service commands/health, and HTTPS inputs. |

**Total: 51 focused tests passed.** The system Python lacked the pinned test
dependencies; after installing the lock into a temporary environment, the
OAuth import also required `DATABASE_URL`. The passing rerun used an explicit
in-memory SQLite URL in that environment. No hosted or Google endpoint was
contacted. No live-browser OAuth, tunnel, Next.js server, Render Blueprint
preview, or hosted resource was started or validated.

## Exact authorization still required

Before the first real Google browser test, the operator must authorize:

1. A short public Quick Tunnel exposure of the loopback frontend, including
   test window, synthetic-data-only use, and immediate shutdown.
2. Google Cloud changes: a separate testing Web client, its audience/test
   account policy, and registration of the exact generated HTTPS callback.
   This is not production client creation or production OAuth enablement.
3. The local-only disposable PostgreSQL bootstrap and explicit migration
   through `0027_storage_lifecycle` (never `head`); no hosted database action
   is included.
4. Injection of the test client secret into the local API process and setting
   `GOOGLE_OAUTH_ENABLED=1` **for this local test only**.

Any Render resource creation/Blueprint apply, hosted database read/bootstrap/
migration, hosted secret injection, production access, or production OAuth
enablement needs separate authorization and is outside this report's
instructions. No such action was taken.

## References

- Google web-server OAuth client and redirect URI guidance:
  <https://developers.google.com/identity/protocols/oauth2/web-server>
- Google OAuth audience and Testing status:
  <https://support.google.com/cloud/answer/15549945>
- Cloudflare Quick Tunnels (public URL, ephemeral hostname, limitations):
  <https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/>
- Render Free service/database/Key Value limits:
  <https://render.com/docs/free>
- Render Key Value authentication and persistence:
  <https://render.com/docs/key-value>
