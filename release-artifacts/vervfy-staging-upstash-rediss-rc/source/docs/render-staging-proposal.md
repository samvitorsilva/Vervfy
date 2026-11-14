# Render staging proposal — review only

**Status: NOT APPROVED FOR DEPLOYMENT.** This proposal is in a separate file
`render.staging.proposal.yaml`; the production `render.yaml` was not changed.
No Render/Google/Supabase resources were accessed or created. Applying a Render
Blueprint would provision only the two staging web services. The owner reports
that an unrelated active Free Redis/Key Value service already occupies the
workspace slot; this proposal neither modifies, deletes, nor references it.
Do not apply the Blueprint until the exact YAML, region, resource inventory,
secrets, and cost are approved.

The approved database target is Supabase project `xgqvwqogdtktgfuubzwk`,
PostgreSQL 17.11, database `postgres`, session pooler
`aws-0-us-east-1.pooler.supabase.com:5432`. The separate Render PostgreSQL 18
database in Oregon must remain unused and untouched. The Blueprint does not
create or configure a PostgreSQL resource; its API `DATABASE_URL` remains a
manual secret, so the file alone does not bind the deployed service to Supabase.
This is a planning-only configuration; **no deployment or database inspection
is authorized**.

## Verified Render project findings — planning only

The owner-reported dashboard inventory is project `Vervfy OAuth Staging`,
with environments `Production` (empty) and `Staging` (containing only
`vervfy-oauth-staging-db`, Render PostgreSQL 18 in Oregon). The owner reports no
environment groups. The current Free plan does not offer Block
cross-environment connections; that control requires a paid plan. These facts
are recorded from the supplied verification; no Render dashboard access was
performed by this task.

The updated Blueprint explicitly places only the two proposed services in
the existing project's `Staging` environment. It omits `Production`, does not
define environment groups, and does not define or modify any PostgreSQL
resource. Confirm in the eventual change preview that Render recognizes the
existing project/environment and shows no Production or database changes.
The owner's active Free Redis/Key Value service is unrelated and out of scope;
do not connect staging to it or change its settings.

## Virginia region revision — planning only

This supersedes the earlier planning-only Oregon selection. The owner approved
the Oregon plan for planning only at `2026-11-11T19:37:13Z`; the subsequent
request changes the proposed region to Virginia and does not approve creation,
deployment, credentials, or database operations.

The API and frontend are pinned to Render region `virginia`.
Render's current Regions documentation lists Virginia, USA; the Blueprint
Specification accepts `virginia`. This aligns the services with the approved
Supabase `us-east-1` endpoint. Render's private network is region-scoped, so
both services remain in Virginia. This does not move or alter the existing
Render PostgreSQL 18 database in Oregon. Provider documentation confirms
Virginia is supported for these service types; confirm the workspace selector
in the Render change preview.

## Proposed staging services

The YAML defines only these Staging-environment services. They have separate
service-scoped configuration, but they are **not network-isolated from
Production** on the current Free plan:

| Service | Proposed name | Purpose |
|---|---|---|
| API | `vervfy-staging-api` | FastAPI backend in Virginia, placed only in the existing Staging environment. |
| Frontend | `vervfy-staging-web` | Next.js same-origin frontend in Virginia, placed only in Staging. Rewrites `/api/*` to the staging API. |

### Session state without Redis

The staging Blueprint deliberately omits `REDIS_URL` and any Key Value
resource. The candidate's `SessionStore` and `RequestThrottle` have
process-local memory implementations. They are appropriate only for this
temporary, single-API-process staging phase with Google OAuth and async uploads
disabled. Sessions and rate-limit counters disappear on restart/redeploy, so
users may need to sign in again and counters reset; do not add API workers or
scale out without a separately approved shared Redis-compatible store. Google
OAuth's one-time transaction store has no memory fallback, so OAuth remains
disabled until an isolated Redis plan and separate approval exist.

A Redis running on the local development computer is useful for local tests only; a Render
service's `localhost` is its own container, not the operator's computer.
Exposing a local instance through port forwarding or a tunnel would add an
unsafe public ingress and uptime dependency, so it is not a practical hosted
staging backend.

Upstash currently lists a $0 Free Redis tier with 250 MB storage, 10 GB monthly
bandwidth, and 500,000 monthly commands
([pricing](https://upstash.com/pricing/redis)). It is technically usable as a
separate TLS-protected service, but introduces a third-party endpoint,
credentials, data processing, quota/region checks, and possible billing
controls. It is not the safest no-additional-cost choice for initial staging;
do not provision it or use the existing workspace Redis without separate
review and approval.

It intentionally does **not** define or manage PostgreSQL. `DATABASE_URL` is a
required manual, service-level value and has no default or production fallback.
When separately authorized, it must target the approved Supabase project above
using the `app_runtime` login, `sslmode=verify-full`, and
`gssencmode=disable`. The API has no
`MIGRATION_DATABASE_URL`; migration credentials belong only in the separately
approved one-off migration runner, never in the long-running API service.

The proposal defines no environment groups, production service references,
Supabase Storage variables, cleanup worker, or worker credential. Keep
`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and
`SUPABASE_BUCKET` absent from the staging API until a separately isolated
staging Storage project/bucket and immutable namespace are approved. Do not
attach any production environment group. Verify the effective service
environment before starting the API.

OAuth is explicitly disabled in the Blueprint (`GOOGLE_OAUTH_ENABLED=0`).
OAuth credentials and `GOOGLE_IDENTITY_LOOKUP_DATABASE_URL` are intentionally
not present in the initial service config; add them only to the API service
after database migrations, role/RLS review, staging isolation checks, and
separate approval. The Google lookup URL must use the dedicated restricted
login, not the application or migration role.

`autoDeploy: false` avoids an automatic service deploy after ordinary
repository updates, but does not prevent a user from explicitly applying the
Blueprint. A custom Blueprint path is needed; do not replace or edit the
production root `render.yaml`. Render documents that a linked Blueprint can
provision and sync resources and can be configured with a custom file path.
The YAML has an explicit `projects` binding for `Vervfy OAuth Staging` /
`Staging`; review the change preview to ensure it targets that existing
environment only.

## Production-access assessment and blockers

Separate Staging services, no environment groups, explicit staging-only
environment values, and distinct least-privilege database credentials reduce
accidental access. They do **not** create a network boundary: on Free, Render
cannot block cross-environment private-network connections. The reported
Production environment is empty today, but future or workspace-level production
services in Virginia may be reachable over Render's shared private network.

The runtime guard is implemented in `staging_database_guard.py` and called by
`db.py` before `create_engine`; invalid staging configuration aborts module
import. When OAuth is enabled, `GoogleOAuthConfig` and `GoogleOAuthService`
apply the same guard to `GOOGLE_IDENTITY_LOOKUP_DATABASE_URL` before creating
its engine. The guard pins the project-reference pooler host, port 5432,
database `postgres`, role-specific project-suffixed login, exact
`sslmode=verify-full&gssencmode=disable` query, approved CA path and SHA-256,
and rejects all other `PG*` connection overrides and TLS trust overrides.
`staging_guard.py` remains a separate operator-operation guard.

**Status: NO-GO for service creation/deployment until the remaining
configuration and approval gates are satisfied:**

1. Keep `DATABASE_URL` as a service-scoped secret pointing only to the
   approved staging Supabase database. Keep `GOOGLE_OAUTH_ENABLED=0`;
   `GOOGLE_IDENTITY_LOOKUP_DATABASE_URL`, all Google credentials,
   `MIGRATION_DATABASE_URL`, and `SUPABASE_*` values remain absent initially.
   Never attach production environment groups.
2. Use a unique staging `VERVFY_SECRET_KEY`; set `VERVFY_ENVIRONMENT=staging`
   and HTTPS-only settings. Leave `REDIS_URL` unset; verify the API runs as a
   single process with OAuth and async uploads disabled. Verify frontend
   `BACKEND_URL` points only to the staging API.
3. Review the change preview for exactly two new Virginia services in the
   existing Staging environment and no changes to Production, PostgreSQL 18,
   or other resources. Confirm workspace Free limits before applying.
4. Separately approve service creation and deployment. The runtime guard
   reduces database misconfiguration risk but does not create Render network
   isolation or authorize a hosted operation.

The Free-plan lack of network isolation remains a residual risk even after
these application checks. The Oregon PostgreSQL 18 database remains out of
scope and must stay unused.

## Staging-only environment variables

### API service

| Variable | Initial proposal | Activation condition |
|---|---|---|
| `VERVFY_ENVIRONMENT` | `staging` | Fixed in YAML; never `production`. |
| `VERVFY_HTTPS_ONLY` | `1` | Fixed in YAML; public requests must use HTTPS. |
| `VERVFY_COOKIE_SAME_SITE` | `lax` | Fixed in YAML; needed for top-level OAuth GET callback. |
| `VERVFY_TRUSTED_PROXY_HOPS` | `1` (tentative) | Confirm Render's actual proxy topology before launch. |
| `VERVFY_SECRET_KEY` | Render-generated unique value | Never copy production key; keep secret in API service only. |
| `VERVFY_ASYNC_UPLOADS` | `0` | No upload worker is included in this auth-focused setup. |
| `PGSSLROOTCERT` | `/etc/secrets/prod-ca-2021.crt` | The approved CA PEM must be uploaded to the API service as a Render Secret File; expected SHA-256 `700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7`. Do not copy it into the repository. Confirm the file is available before launch. |
| `DATABASE_URL` | Manual secret for `app_runtime` on Supabase project `xgqvwqogdtktgfuubzwk`, endpoint `aws-0-us-east-1.pooler.supabase.com:5432`, database `postgres` | Must include `sslmode=verify-full&gssencmode=disable` and use the approved CA via `PGSSLROOTCERT`. The Blueprint does not contain a URL or password; the local CA path is not a Render path. The application guard rejects any other staging endpoint/configuration before creating its engine. If certificate validation cannot be established, startup fails; do not use the Render PostgreSQL 18 endpoint. |
| `REDIS_URL` | Absent for initial staging | The single API process uses its in-memory session allowlist and rate limiter. State resets on restart/redeploy; keep OAuth disabled and do not scale out. Never reference the Render workspace’s existing Free Redis/Key Value service. |
| `GOOGLE_OAUTH_ENABLED` | `0` | Only change to `1` through a separately approved staging-only action after all pre-enable gates pass. |
| `GOOGLE_CLIENT_ID` | Not initially set | Add the staging Web OAuth client ID to API service only after approval. |
| `GOOGLE_CLIENT_SECRET` | Not initially set | Add via secret store to API only; never frontend, build args, logs, or repository. |
| `GOOGLE_FRONTEND_ORIGIN` | Not initially set | Exact public HTTPS staging frontend origin, no path/trailing slash. |
| `GOOGLE_REDIRECT_URI` | Not initially set | Exact callback below; must match Google Console byte-for-byte. |
| `GOOGLE_IDENTITY_LOOKUP_DATABASE_URL` | Not initially set | Add only after migrations, role/RLS review, and separate approval. It must use the dedicated `google_auth_lookup` login on the approved Supabase project, with `sslmode=verify-full` and the API's approved CA. OAuth remains disabled initially. |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET` | Absent | Do not use production Supabase. For auth-only tests, keep Storage unconfigured. Configure only after a distinct staging Storage project/bucket/namespace is independently verified. |
| `MIGRATION_DATABASE_URL` | Absent | One-off guarded migration environment only, with separate approval; never deploy into API service. |

### Frontend service

| Variable | Staging value |
|---|---|
| `BACKEND_URL` | Exact public HTTPS origin of `vervfy-staging-api`, not production and not the frontend's own host. It is required at Next.js build time for rewrites. |
| `SITE_URL` | Exact public HTTPS origin of `vervfy-staging-web`; no credentials or paths. |

Render Free web services cannot receive private-network traffic, so this
proposal uses the staging API's public HTTPS URL for the frontend rewrite.
Keep browser requests same-origin through the frontend. Do not configure a
production backend in `BACKEND_URL`. Both web services are public; test with
synthetic accounts and enable available staging access controls before
credentials are added.

No separate upload worker is included. `VERVFY_ASYNC_UPLOADS=0` avoids relying
on one for this authentication test. Do not deploy the cleanup worker or enable
physical deletion.

## Storage adapter decision

The local filesystem adapter is **not appropriate for Render staging**:

- It explicitly requires `VERVFY_ENVIRONMENT=local-test`,
  `VERVFY_STORAGE_BACKEND=filesystem`, a disposable PostgreSQL Unix socket,
  no Supabase settings, and a local test storage root under `/tmp`.
- Render's default filesystem is ephemeral; changes are lost on restart or
  redeploy. A persistent disk would preserve only mounted files for its
  attached service and is not shared object storage or a cross-service backup.
- Do not set `VERVFY_STORAGE_BACKEND=filesystem` on Render. For authentication
  tests, leave Supabase storage unset and do not test media features. For
  hosted storage security testing, separately provision and approve a dedicated
  staging Supabase project/private bucket and immutable DB namespace. Never
  point staging at production Storage. Physical cleanup remains disabled.

## OAuth callback and Google Cloud checklist

After the staging frontend hostname is issued and independently verified, use
exactly:

```text
https://<STAGING_FRONTEND_HOST>/api/auth/google/callback
```

Set `GOOGLE_FRONTEND_ORIGIN` to `https://<STAGING_FRONTEND_HOST>` and
`GOOGLE_REDIRECT_URI` to the full URI above, on the staging API only. Register
that exact redirect URI in Google Cloud. If this OAuth client setup requires
an authorized JavaScript origin, add only the exact staging frontend origin.
Do not register wildcards, production hosts, API/private hosts, or alternate
paths.

Manual Google Cloud actions (owner approval required):

1. Use a distinct approved Google Cloud project/client for staging; create a
   Web application OAuth client, not a production client copy.
2. Set the consent-screen audience/test-user policy and restrict login to
   explicitly approved staging testers. Use controlled test identities and
   synthetic Vervfy profiles; do not add unapproved users.
3. Configure the exact callback URI and, only if required, the exact authorized
   JavaScript origin. Review branding/verification requirements and the
   requested minimal `openid email profile` scopes; do not enable unrelated
   APIs or broaden scopes.
4. Store the client secret only in the staging API secret store. Keep OAuth
   disabled while services and database are being prepared.
5. After separately approved migrations and role/RLS checks, set the dedicated
   lookup URL and enable OAuth only for the staging API. Verify callback,
   replay, browser binding, state/nonce/PKCE, token validation, account
   registration/linking, Redis outage, and logs per the OAuth runbook.

## Ordered setup plan and approval gates

1. **Isolation evidence — owner/operator action, required before any DB access.**
   Confirm the Vervfy staging workspace and `Vervfy OAuth Staging` project in the Render
   change preview, review the new service IDs and environment groups, and verify
   no production resource or credential is attached. The only approved database
   target is Supabase project `xgqvwqogdtktgfuubzwk`; the existing Render
   PostgreSQL 18 database in Oregon is excluded and remains untouched. Do not
   connect to hosted PostgreSQL until separately authorized.
2. **Exact configuration review — user approval required.** Confirm the
   custom Blueprint path, the two resource names, Virginia region for both
   services, plans, staging `BACKEND_URL`, expected environment variables,
   CA-file setup, in-memory session semantics, and total cost. Render's region is immutable after creation;
   the Supabase session-pooler endpoint identifies the approved database as
   `us-east-1`. Keep the older Render PostgreSQL 18 database in Oregon unused.
3. **Infrastructure creation — manual dashboard action, separate approval
   required.** Applying the Blueprint creates only the staging web/API in
   Virginia. It does not create PostgreSQL or Redis/Key Value. Review the complete Render
   change-preview and verify no production service, environment group, or
   credential is attached and the existing Oregon PostgreSQL 18 resource is
   unchanged. Confirm no `REDIS_URL` override is set and do not attach the
   existing workspace Redis service.
4. **Set service secrets — manual dashboard action, user/operator approval.**
   Set staging `DATABASE_URL` with app role and correct TLS. Confirm no shared
   environment group is attached and no production values are present. Leave
   OAuth and all Google variables off/absent. Do not add migration credentials
   to API.
5. **Migration authorization — separate DBA/release approval required; blocked
   now.** Current application startup checks require the reviewed 0027 storage
   reference guards. Google login requires provider identity migrations
   including 0022. The current local chain includes 0027/0028, which remain
   unapproved for hosted execution. Do not deploy this code against an
   unverified or unmigrated database; do not run migrations as part of this
   proposal.
6. **Storage project decision — manual approval required for any media tests.**
   Initial proposal leaves storage disabled. Before media/storage tests, prove
   a separate staging Supabase project/bucket and namespace, then supply
   staging-only values. No physical deletion.
7. **Google client setup — Google Cloud owner action and user approval.**
   Follow the checklist above after the frontend host is known. Obtain approval
   before adding the secret or turning OAuth on.
8. **Prelaunch verification — separate go/no-go approval.** Verify deployed
   revision, database migration state (only after separately authorized
   read-only inspection), roles/RLS, in-memory session behavior across restart,
   frontend rewrite, HTTPS/cookies, account access restrictions, and staging
   logs. Only synthetic identities/data. Stop on any uncertainty.
9. **Cleanup — owner action.** After test window, disable OAuth, stop/remove
   staging resources under an approved retention plan. Do not invoke cleanup
   worker or physically delete objects without separate approval.

## Minimum infrastructure and cost estimate

The initial password-only staging phase does not provision Redis. A future
Google OAuth phase additionally requires a dedicated Redis-compatible store
for one-time transaction state; that resource and its credentials need a
separate plan and approval.

Minimum for realistic browser-based Google registration/login:

- The approved Supabase PostgreSQL 17.11 database, project
  `xgqvwqogdtktgfuubzwk`, endpoint `aws-0-us-east-1.pooler.supabase.com:5432`.
  This Blueprint does not create or manage it. Its plan/charge is separate and
  not included; the existing Render PostgreSQL 18 database in Oregon stays
  unused.
- One dedicated staging Redis-compatible store, approved separately. Never
  reuse or share the Render workspace’s existing Redis/Key Value service.
- Separate public HTTPS staging API and frontend services so the Next rewrite,
  Render proxy/cookies, and exact Google callback are exercised.
- One distinct Google Web OAuth client and controlled tester accounts.
- Separate staging secrets and no production environment groups/credentials.
- No Supabase Storage needed for auth-only tests. A separate staging bucket is
  an additional prerequisite for media/storage tests.

Indicative Render costs from the existing runbook's 2026-11-03 published-price
check (not a quote; confirm current dashboard pricing/quotas):

| Option | Estimate | Caveats |
|---|---:|---|
| Free/short password-only test window | Potentially `$0` incremental for two Free web services if workspace hours and quotas are available; database charges excluded | Free web services sleep after 15 minutes; shared 750 monthly instance hours/build minutes/bandwidth. No new Redis/Key Value service. The unused Render PostgreSQL 18 charge, if any, continues separately. In-memory sessions/rate limits reset on restarts. |
| Always-on minimum web | About `$14/month` for two `$7/month` web services, plus database charges | Indicative price snapshot from the existing 2026-11-03 estimate; no Redis cost included. Taxes, usage, bandwidth/build overages, and current workspace pricing are excluded; confirm in Render's change preview. |

The Supabase PostgreSQL 17 plan/charge and the existing Render PostgreSQL 18
plan/charge are not included. No resources are provisioned by this task.

## Approval required

Before any deployment, user approval is required for the exact YAML and
service/region/cost selection. Separate manual owner actions are required for
Render resource creation and secrets, verifying database identity/isolation,
any database migration, staging Supabase setup, and Google Cloud OAuth client
creation. Enabling staging OAuth is a separate go/no-go decision after all
pre-enable checks. Production settings, credentials, data, and OAuth remain
untouched.

## References

- [Render Blueprint specification](https://render.com/docs/blueprint-spec)
- [Render Key Value / Valkey](https://render.com/docs/key-value)
- [Render ephemeral and persistent filesystems](https://render.com/docs/disks)
- [Google OAuth 2.0 for web server applications](https://developers.google.com/identity/protocols/oauth2/web-server)
- Existing local contract: `docs/google-oauth-staging-runbook.md`,
  `docs/google-oauth-readiness.md`, `docs/staging-endpoint-approval.md`, and
  `docs/storage-lifecycle.md`.
