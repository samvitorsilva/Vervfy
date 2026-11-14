# Vervfy staging deployment approval package

**Status: DRAFT — no new approval recorded; no actions authorized.**

> **SUPERSEDED — DO NOT USE THIS PACKAGE FOR DEPLOYMENT OR APPROVAL.**
> The Free Key Value slot is occupied. The three-service candidate, hashes,
> capacity assumptions, and draft approval wording below describe an older
> snapshot and are not the current staging plan. See
> [Occupied-slot staging plan](staging-occupied-key-value-plan.md). The
> current working proposal is a two-web-service draft and differs from the
> archived candidate; a new frozen candidate and verification are required
> before any future approval or deployment. The remaining text is historical.


Updated for owner review at `2026-11-11T21:19:29Z`. This package keeps
database changes, code publication, Render resource creation, and deployment
as distinct approval scopes. Confirm each scope separately; set its UTC
validity window at confirmation, no longer than 24 hours.

## Candidate and fixed staging target

- Candidate archive:
  `release-artifacts/supabase-pg17-oauth-rc/vervfy-supabase-pg17-oauth-rc-virginia-staging-runtime-guard.tar.gz`
  — SHA-256
  `aa109740381cc3abb0c9e3690c1ff7f60d04ccfd11bec4a71d62ec2d48aefa23`.
- Manifest:
  `release-artifacts/supabase-pg17-oauth-rc/candidate-manifest-virginia-staging-runtime-guard.json`
  — SHA-256
  `4080312c91e5737fc815d38d8a5f7612aca32fa82a3f51edfb8a7fe079ed8aa9`;
  258 source files, verified against the archive.
- Default-privilege SQL:
  `source/docs/staging-migration-default-privileges.sql` — SHA-256
  `dc1d796c86bac26308058bc59eee5257b6b1dee055e71abbfbaf55ea37865e0b`.
- Supabase staging: project `xgqvwqogdtktgfuubzwk`,
  `aws-0-us-east-1.pooler.supabase.com:5432`, database `postgres`.
- Approved CA: `/home/sam/Downloads/prod-ca-2021.crt`, SHA-256
  `700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7`.

The existing credential/default-privilege approval is still within its
recorded time window, but binds the earlier archive and manifest hashes
`0fc5bd26bd4b8245e1fbed2f0e6fb6a1211decdd84f1843d918355021f809aa2` and
`b508be0f2ddc9c37fef0febc1f013feb2788a43271c91ac1253fda825a563ad6`.
Do not use it for this candidate. The SQL hash is unchanged; obtain
replacement approval binding the current archive, manifest, and SQL hashes.

## Initial runtime configuration

On `vervfy-staging-api`, use:

- `VERVFY_ENVIRONMENT=staging`
- `PGSSLROOTCERT=/etc/secrets/prod-ca-2021.crt`
- `DATABASE_URL` as a service secret for
  `app_runtime.xgqvwqogdtktgfuubzwk` at the endpoint above, with
  `sslmode=verify-full&gssencmode=disable`. Its non-secret shape is
  `postgresql://app_runtime.xgqvwqogdtktgfuubzwk:<url-encoded-password>@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=verify-full&gssencmode=disable`.
- `GOOGLE_OAUTH_ENABLED=0`; leave
  `GOOGLE_IDENTITY_LOOKUP_DATABASE_URL` unset for initial launch.
- `VERVFY_HTTPS_ONLY=1`, `VERVFY_COOKIE_SAME_SITE=lax`,
  `VERVFY_ASYNC_UPLOADS=0`, a unique Render-generated `VERVFY_SECRET_KEY`,
  and the Staging Valkey `REDIS_URL` reference. Confirm the tentative
  `VERVFY_TRUSTED_PROXY_HOPS=1` against Render's proxy topology.

Deliver the CA through **API service → Environment → Secret Files**, filename
`prod-ca-2021.crt`; do not commit it or put it in Blueprint YAML. Render
documents that saving a Secret File triggers a deployment. The runtime
`GOOGLE_IDENTITY_LOOKUP_DATABASE_URL`, when separately approved and ready,
belongs as an API service secret using the distinct
`google_auth_lookup.xgqvwqogdtktgfuubzwk` login and the same verified TLS
settings; its non-secret URL shape uses that login in place of `app_runtime`.
It is not a frontend variable.

Proposed password destinations are the API service secrets `DATABASE_URL`
and, only in a later approved phase, `GOOGLE_IDENTITY_LOOKUP_DATABASE_URL`.
The one-off `vervfy_oauth_staging_user` credential must not be put in either
service. The owner selected GNOME Keyring (Secret Service), dedicated item
`Vervfy Staging Migration DB`, for that one-off credential, and requires
encryption/locking verification before any value is stored. The Render
service-scoped variables and API Secret File do not exist yet. Verify each
destination and the secure transfer path after service creation and before
provisioning or transfer. Never put password values in this document, the
repository, or logs.

Read-only local keyring inspection found `login.keyring` owned by `sam` with
mode `0600` and AES encryption, but its metadata reports hash type MD5 and
“not locked if idle”; the Secret Service collection currently reports
`Locked=false`. No item was read or written. This does **not** meet the
requested locking check; do not store credentials until the owner configures
and verifies an appropriate lock policy and accepts the keyring format, or
selects another approved vault.

## Final initial-deployment checks

- **Canonical Blueprint:** use only
  `release-artifacts/supabase-pg17-oauth-rc/source/render.staging.proposal.yaml`.
  It defines exactly three resources under `Vervfy OAuth Staging` → `Staging`:
  API, web, and Valkey, each Virginia/Free. It defines no database or
  Production resources. Do not select the older
  `phase4a-retry-limits/render.staging.proposal.yaml`; that planning file
  contains Oregon/PostgreSQL 18 resources and is not the approved candidate.
- **Free Key Value capacity:** not confirmed. No Render CLI is available in
  this environment and no authenticated workspace inventory was accessible.
  The owner must inspect the entire Hobby workspace (all projects/environments)
  and confirm zero active Free Key Value instances before approval.
- **Frontend isolation: guard implemented and locally verified.** The previous
  local build routed auth/API requests to production from `web/.env.local` and
  `.next/routes-manifest.json`; this was a real misconfiguration risk. The
  candidate now sets `VERVFY_ENVIRONMENT=staging` on the web service. Its
  Next.js config fails the build unless `BACKEND_URL` is exactly
  `https://vervfy-staging-api.onrender.com` and `SITE_URL` is exactly
  `https://vervfy-staging-web.onrender.com`, both without extra paths or URL
  credentials. The production API origin is rejected. Five focused URL-guard
  tests passed, targeted ESLint passed, and a Next.js production build with
  those staging origins succeeded; the generated rewrite manifest contained
  only `https://vervfy-staging-api.onrender.com`. These are expected origins
  from the proposed service names, not verified live Render hostnames. Confirm
  the actual hostnames and exact Preview values before applying; any mismatch
  must fail the build, not be replaced with a production fallback. The web
  service remains public; password-authentication UI exists, but with the API
  expected to fail startup before database connection it is not usable. Google
  OAuth remains disabled.
- **Expected API first start:** with the CA Secret File absent, the staging
  runtime guard should fail before database engine creation or any connection.
  The web URL guard independently prevents the production API destination.

## Separate approvals requested

Each item below is a separate draft scope, not an approval. None authorizes
any other item.

1. **Database credential provisioning:** after the secret destination/write
   path is confirmed, set distinct passwords only for
   `vervfy_oauth_staging_user`, `app_runtime`, and `google_auth_lookup` using
   hidden prompts; store each only in its confirmed destination. No SQL,
   deployment, OAuth, or production access.
2. **Default-privilege SQL:** execute only the hash-bound SQL above as
   `vervfy_oauth_staging_user` against the stated Supabase staging target.
   No other SQL, migrations, namespace setup, or role changes.
3. **Candidate publication:** publish the reviewed candidate and manifest to
   a dedicated branch, proposed name
   `staging/vervfy-pg17-runtime-guard-20261111`, including the extracted
   candidate source tree used by `rootDir` and
   `source/render.staging.proposal.yaml`. Link Render to that Blueprint path.
   No Blueprint sync or deploy.
4. **Render service creation and Blueprint's initial deploy:** apply only the
   reviewed Blueprint to `Vervfy OAuth Staging` → `Staging`, creating exactly
   `vervfy-staging-api`, `vervfy-staging-web`, and `vervfy-staging-valkey`
   in Virginia on Free plans. No Production, PostgreSQL, or environment-group
   changes. This scope must explicitly acknowledge the Blueprint's initial
   deployment, public API/web Render hostnames, and expected API startup
   failure before database connection because the CA is not attached yet.
   The initial web build must use the exact origins enforced by the candidate;
   verify actual Render hostnames and change-preview values before proceeding.
5. **CA/secret configuration and resulting redeploy:** after creation, add
   the approved CA Secret File and only the approved service-scoped secret
   values, then authorize the deployment triggered by saving the file.
   Keep OAuth disabled and the Google lookup URL absent.

Do not treat the current `autoDeploy: false` as a way to suppress the initial
deployment: Render documents it as disabling automatic commit-triggered
deploys. Render's dashboard guide says clicking **Deploy** creates a web
service and kicks off its first deploy; the Blueprint guide says **Deploy
Blueprint** begins provisioning defined resources. No documented, Hobby-
compatible workflow was found to create these services without the initial
deployment. Because the CA Secret File is added after the API service exists
and its save triggers another deploy, the first API start will lack the CA
file and the runtime guard should fail closed before any database connection.
The owner is willing to consider the initial deployment subject to final
verification. Current execution remains **NO-GO** because the Free Key Value
slot is unverified and the candidate is unpublished, so no Render change
preview or actual service hostnames are available for final verification. Do
not use `autoDeploy: false` as a workaround.

### Fail-closed first boot alternative (evaluation only)

No policy change is recorded. With `VERVFY_ENVIRONMENT=staging`, the API's
module import validates `DATABASE_URL` and the CA before creating the SQLAlchemy
engine. If the Blueprint's first launch occurs before the CA Secret File is
attached, API import should fail before any database connection. The upload
worker imports the same guarded `db` module; the proposed Blueprint has no
worker service and sets `VERVFY_ASYNC_UPLOADS=0`. OAuth is off by default; an
enabled but incomplete config fails, and a staging lookup URL with a missing
CA fails before its engine is created.

Focused verification: `tests/test_staging_database_guard.py` and
`tests/test_google_oauth.py` passed (30 tests, 26 subtests). Three additional
offline negative-startup checks passed for API import, upload-worker import,
and Google lookup engine creation with a missing CA. No database or hosted
service was contacted. This alternative leaves the API unavailable on its first start; web and
Valkey may still be provisioned, and the web service has a public Render
hostname. The CA upload triggers a distinct redeploy. The owner is now willing
to consider this initial deployment, subject to the final checks above; no
deployment approval has been recorded.

If the owner confirms the final checks above, the narrowly scoped approval to
review would be:

> I approve applying the reviewed Vervfy staging Blueprint at
> `release-artifacts/supabase-pg17-oauth-rc/source/render.staging.proposal.yaml`
> from candidate archive SHA-256
> `aa109740381cc3abb0c9e3690c1ff7f60d04ccfd11bec4a71d62ec2d48aefa23`
> and manifest SHA-256
> `4080312c91e5737fc815d38d8a5f7612aca32fa82a3f51edfb8a7fe079ed8aa9`
> to `Vervfy OAuth Staging` → `Staging` to create only
> `vervfy-staging-api`,
> `vervfy-staging-web`, and `vervfy-staging-valkey` in Virginia on Free,
> including the initial deployment triggered by Blueprint application, only
> after separate approval and publication of this exact candidate, confirmation
> that the Free Key Value slot is available, and a change preview showing
> exactly those services. I
> authorize the initial web deployment only after verifying the actual Render
> hostnames and change-preview values match the candidate's staging-only
> `BACKEND_URL`/`SITE_URL` allowlist, and the generated frontend routes contain
> no production host; otherwise do not deploy. I acknowledge that the API is expected to fail
> startup before any database connection because its CA Secret File is
> attached afterward, and that the API and web receive public Render
> hostnames. Google OAuth remains disabled; password authentication is not
> authorization to access Production. This approval excludes code
> publication, credentials, CA delivery or its later redeploy, SQL,
> migrations, Production, and every other resource. Approval ID and UTC
> validity window remain pending explicit confirmation after the Free Key
> Value slot and live hostname checks are verified. This is not yet approval
> to execute.

## Remaining verification blockers

- **Free capacity:** The owner reports the Render Hobby workspace at 257.4/750
  Free instance-hours used (492.6 remaining), 3/25 included services,
  19 MB/5 GB bandwidth, and 1/500 build-pipeline minutes. No extra spending is
  approved. The single active Free Key Value slot remains unverified; confirm
  that it is available before approval. Also confirm billing/spend controls
  prevent unapproved bandwidth or build-pipeline overage charges; otherwise
  do not apply the Blueprint.
- **Free Key Value and spend cap:** Render allows Free Key Value on Hobby, but
  only one active Free Key Value is allowed per workspace, so the workspace
  slot still needs checking. Free Key Value is in-memory and loses data on
  restart. To check the slot, select the Render Hobby workspace, inspect the
  workspace-wide resource list (all projects/environments) for an active Free
  Key Value, and confirm none exists. Render's documented spend limit caps
  only build-pipeline overages; set a $0 monthly pipeline spend limit if the
  dashboard accepts it. This is not a general spending cap: bandwidth
  overages may be billed when a payment method is present. No workspace-wide
  hard cap was identified in the reviewed Render documentation.
- **Publication:** the candidate is currently local/untracked. Do not select
  Deploy Blueprint until the dedicated branch contains the reviewed candidate
  and the change preview shows only the three resources above.
- **Network boundary:** Free-plan cross-environment network isolation is
  unavailable. Keep production untouched; the Oregon PostgreSQL 18 instance
  remains unused. Google OAuth stays disabled.
- **Credential readiness:** GNOME Keyring encryption/locking and the secure
  transfer path are not yet acceptable/verified; the current keyring is
  unlocked and marked not to lock when idle. Render secret destinations do not
  exist until the API service is created. Do not provision or transfer
  credentials until both are verified.
- **Alternative local vault:** KeePassXC with a dedicated local KDBX vault,
  strong unique master passphrase, Argon2id key derivation, and auto-lock on
  idle/screen lock is proposed for one-off operator credentials. Minimum
  setup: install KeePassXC from its official source; create a local KDBX
  database outside the repository; choose Argon2id and a strong unique master
  passphrase; enable the available idle/minimize auto-lock and short clipboard
  clearing; test screen/session-lock behavior and manually lock before leaving
  the session if it is not integrated. Lock/reopen the empty vault to verify
  those settings before storing anything. Do not sync the vault to a shared
  drive. Runtime URLs still belong only in the API's Render service secrets.

Render references:
[Blueprints](https://render.com/docs/infrastructure-as-code),
[Blueprint specification](https://render.com/docs/blueprint-spec),
[first deploy](https://render.com/docs/your-first-deploy),
[Free instances](https://render.com/docs/free), and
[environment variables and Secret Files](https://render.com/docs/configure-environment-variables).
