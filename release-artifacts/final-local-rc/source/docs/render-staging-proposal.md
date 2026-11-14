# Render staging proposal — review only

**Status: NOT APPROVED FOR DEPLOYMENT.** This proposal is in a separate file
`render.staging.proposal.yaml`; the production `render.yaml` was not changed.
No Render/Google/Supabase resources were accessed or created. Applying a Render
Blueprint would provision the two web services and a new Valkey service, so do
not apply it until the exact YAML, region, resource inventory, secrets, and
cost are approved.

The known staging database `vervfy-oauth-staging-db` is reported to exist and
to be unused, but its project/resource ID, hostname, region, plan, credentials,
and data provenance have not been independently verified. Previous isolation
review found that production/staging separation could not be established.
Therefore this is a configuration proposal only; **no deployment or database
inspection is authorized**.

## Proposed isolated services

The YAML defines only:

| Service | Proposed name | Purpose |
|---|---|---|
| API | `vervfy-staging-api` | FastAPI backend. Separate service-scoped environment; never attach production environment groups. |
| Frontend | `vervfy-staging-web` | Next.js same-origin frontend and OAuth callback host. Rewrites `/api/*` to the staging API. |
| Key Value | `vervfy-staging-valkey` | Dedicated Valkey for sessions, rate limits, and one-time OAuth transaction state. `noeviction` fails writes instead of evicting authentication state. |

It intentionally does **not** define or manage PostgreSQL, because the staging
database is reported to already exist. `DATABASE_URL` is a required manual,
service-level value and has no default or production fallback. The API has no
`MIGRATION_DATABASE_URL`; migration credentials belong only in the separately
approved one-off migration runner, never in the long-running API service.

The proposal defines no shared environment groups, no production service
references, no Supabase environment variables, no storage cleanup worker, and
no worker credential. Keep `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and
`SUPABASE_BUCKET` absent from the staging API until a separately isolated
staging Storage project/bucket and immutable namespace are approved. Do not
attach any Render environment group containing production credentials. Verify
the effective service environment before starting the API.

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
The proposed YAML must be reviewed in the Render change preview before any
manual deployment approval.

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
| `DATABASE_URL` | Manual secret: verified staging PostgreSQL endpoint and `app_runtime` login only | Must point to the separately verified `vervfy-oauth-staging-db`; require certificate-verified TLS (`sslmode=verify-full`) with its approved CA where supported. The application does not force TLS for `staging`, so TLS must be verified in the URL and by a post-launch connection check. If certificate validation cannot be established, stop; do not silently downgrade. Missing value fails startup. Never use a production URL. |
| `REDIS_URL` | Internal connection URL from `vervfy-staging-valkey` | Blueprint reference points only to the dedicated staging Valkey. Keep same Render region. Enable internal authentication in Render and confirm this reference resolves to the authenticated staging URL before testing. Do not enable external access. |
| `GOOGLE_OAUTH_ENABLED` | `0` | Only change to `1` through a separately approved staging-only action after all pre-enable gates pass. |
| `GOOGLE_CLIENT_ID` | Not initially set | Add the staging Web OAuth client ID to API service only after approval. |
| `GOOGLE_CLIENT_SECRET` | Not initially set | Add via secret store to API only; never frontend, build args, logs, or repository. |
| `GOOGLE_FRONTEND_ORIGIN` | Not initially set | Exact public HTTPS staging frontend origin, no path/trailing slash. |
| `GOOGLE_REDIRECT_URI` | Not initially set | Exact callback below; must match Google Console byte-for-byte. |
| `GOOGLE_IDENTITY_LOOKUP_DATABASE_URL` | Not initially set | Dedicated TLS `google_auth_lookup` login to the staging database; distinct from app and migration principal. Require `sslmode=verify-full` and approved CA evidence where supported; OAuth's staging config does not automatically force PostgreSQL TLS. |
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
   Verify Render resource IDs, database hostname/project and region, staging
   credentials, service environment groups, and that no staging worker/service
   can target production DB, Redis, or Supabase. Confirm the reportedly unused
   database is empty/disposable through approved inventory evidence. Do not
   connect to hosted PostgreSQL until separately authorized.
2. **Exact configuration review — user approval required.** Confirm the
   custom Blueprint path, resource names, Render region (must match Valkey and
   database connectivity), plans, `BACKEND_URL`, expected environment
   variables, and total cost. No region is hard-coded because the existing
   database's region is unknown.
3. **Infrastructure creation — manual dashboard action, separate approval
   required.** Applying the Blueprint creates the staging web/API and Valkey
   resources. It does not create PostgreSQL. Choose the exact Render region
   matching the existing staging DB/Valkey connectivity before applying.
   Review the complete Render change-preview and verify no production service
   is modified or reused. Enable Valkey internal authentication and keep
   external access disabled.
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
   read-only inspection), roles/RLS, Redis isolation, frontend rewrite,
   HTTPS/cookies, account access restrictions, and staging logs. Only synthetic
   identities/data. Stop on any uncertainty.
9. **Cleanup — owner action.** After test window, disable OAuth, stop/remove
   staging resources under an approved retention plan. Do not invoke cleanup
   worker or physically delete objects without separate approval.

## Minimum infrastructure and cost estimate

Minimum for realistic browser-based Google registration/login:

- One staging PostgreSQL database (reported as existing; plan, region, empty
  state, backups, and monthly charge unknown).
- One dedicated staging Valkey/Key Value instance (do not reuse production
  `vervfy-redis`).
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
| Free/short test window | Potentially `$0` incremental for two free web services and free Key Value if workspace slots, hours, and quotas are available; existing PostgreSQL charge excluded/unknown | Free web services sleep after 15 minutes; shared 750 monthly instance hours/build minutes/bandwidth; Free Key Value has 25 MB and loses keys on restart; Free Postgres is 1 GB, expires after 30 days, and has no backups. Production may already consume workspace free slots. |
| Always-on minimum web + Valkey | About `$24/month` for two `$7/month` web services plus `$10/month` Key Value, **plus the existing staging PostgreSQL plan/charge** | Price snapshot only; taxes, usage, bandwidth/build overages, and any DB upgrades excluded. Prior runbook estimated about `$30/month` including a new `$6/month` smallest PostgreSQL; that DB is reportedly already provisioned here but actual billing is unknown. |

No database pricing is included because the existing resource's plan is
unknown. No resources are provisioned by this task.

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
