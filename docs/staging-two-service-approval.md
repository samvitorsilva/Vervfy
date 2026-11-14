# Two-service staging approval draft

NOT APPROVED. No publication, credentials, SQL, service creation or deployment is authorized.

Candidate archive: `release-artifacts/supabase-pg17-oauth-rc/vervfy-two-service-virginia.tar.gz`
SHA-256: `e8955737b79cc47f01510fad610dd02af2c80579d8059e305f625b44f4916462`

Manifest: `release-artifacts/supabase-pg17-oauth-rc/candidate-manifest-two-service-virginia.json`
SHA-256: `2f4db5dc46dbd2de8272ea0253c089a4b4930b8ec4975f023169975434886c7a`

All 260 archived files match their manifest hashes and working source bytes.
The snapshot preserves existing candidate files, with a pre-import staging session guard,
explicit one-worker startup, and focused session tests. Production code outside the
candidate was not changed. This supersedes the older three-service approval package.

Proposed resources: only vervfy-staging-api and vervfy-staging-web, Virginia, Free.
Redis must be absent even from inherited environment configuration. OAuth and async
uploads must be explicitly disabled. Staging startup rejects conflicting settings
before application/database imports. Sessions are process-local allowlisted IDs:
restart invalidates them, logout revokes them, and throttles reset on restart.
No multiple workers, replicas, or production-equivalent availability claims.

Preserve the existing approved Supabase PG17 staging project, restricted runtime
role and pinned CA verification. Do not access or share existing production Redis.
Verify no production environment group, credential, database or storage is attached.
Free-tier shared hours and bandwidth/build billing require review; no added spending
is approved. Candidate creation does not authorize running migrations or SQL.

For later hosted Google OAuth testing, the minimum additional infrastructure is
one dedicated staging Redis-compatible service reachable by the API over verified
TLS, with separate credentials and no production data or Redis sharing. Review free
tier limits, billing, supported atomic commands, expiry, outage behavior and region.
Also require the separate staging Google OAuth client, exact HTTPS callback and
approved restricted identity-lookup configuration. No such credentials are created.
Local Redis is suitable for local tests, not recommended through a public tunnel.

Before deployment approval: review the exact hashes and two-resource change preview,
confirm effective one-worker configuration and staging hostnames, check cost limits,
and separately authorize publication, secret delivery and initial deployment.
The API may remain unready until separately authorized database prerequisites and
CA delivery are complete. No hosted readiness or OAuth success is claimed.

Local validation: `tests/test_staging_session_guard.py` and `tests/test_staging_database_guard.py`: 13 passed, 16 subtests passed. No full integration or hosted tests were run. Session classes were tested directly without database imports.

## Final approval process — 2026-11-11

Archive and manifest hashes above were reverified, including all 260 archive
entries and the reviewed deployment files. No completed tests were rerun.
The candidate remains unchanged. Live Render bindings, quota, hostname availability,
secret delivery and database readiness have not been verified.

### Exact publication scope

Proposed repository: `https://github.com/samvitorsilva/Verfy.git`.
Proposed dedicated branch: `staging/two-service-virginia` (not production/main).
Publish only the frozen source, archive, manifest and checksum sidecars, preserving
`release-artifacts/supabase-pg17-oauth-rc/source/` as the source location. Do not
publish the unrelated working-tree changes. Before pushing, prepare an isolated
commit from the archive, verify every source byte against the manifest, inspect
branch workflows for unintended deployment triggers, and record the commit ID.
Publication approval must name the repository, branch and that exact commit.
No push or commit has been performed by this review.

### Render binding and configuration

Use custom Blueprint path
`release-artifacts/supabase-pg17-oauth-rc/source/render.staging.proposal.yaml`.
Require the preview to show exactly two NEW web services in project
`Vervfy OAuth Staging`, environment `Staging`:

| Service | Runtime | Region | Plan | Root |
| --- | --- | --- | --- | --- |
| vervfy-staging-api | Python | virginia | free | release-artifacts/supabase-pg17-oauth-rc/source |
| vervfy-staging-web | Node | virginia | free | release-artifacts/supabase-pg17-oauth-rc/source/web |

Select only the approved dedicated branch/commit. Stop for resource adoption,
name suffixes, different hostnames, paid plans, production changes, or extra
resources. Verify workspace/project/environment IDs in the live preview; names
alone are not proof of binding. Attach no shared production environment group.
Set Blueprint Auto Sync to No; service autoDeploy is already false. Initial
Blueprint application still creates and deploys the services.

API inputs: authorize only a newly generated service-scoped `VERVFY_SECRET_KEY`
(the Blueprint has `generateValue: true`) and delivery of the existing approved
staging `DATABASE_URL`, using role `app_runtime` on Supabase project
`xgqvwqogdtktgfuubzwk`, session pooler `aws-0-us-east-1.pooler.supabase.com:5432`,
database `postgres`, `sslmode=verify-full&gssencmode=disable`. No new database
credential, role, rotation, or SQL is included. Never print or commit the URL.
`REDIS_URL` must be absent, not an empty variable. OAuth and async uploads are
`0`; the start command pins `--workers 1`. Reject conflicting inherited settings.
Do not supply OAuth, migration, production Redis or production storage credentials.

Web inputs (available at build time):
`BACKEND_URL=https://vervfy-staging-api.onrender.com` and
`SITE_URL=https://vervfy-staging-web.onrender.com`.
Both services have `VERVFY_ENVIRONMENT=staging`. Different actual hostnames require
candidate changes and new hashes, not a workaround to the frontend guard.

### CA and initial deployment sequence

The Blueprint only sets `PGSSLROOTCERT=/etc/secrets/prod-ca-2021.crt`; it does
not upload that file. Deliver the approved CA to the API as a service-only
secret file named `prod-ca-2021.crt`. Expected SHA-256:
`700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7`.
Verify the local approved file hash before delivery. Do not bypass certificate
validation or copy secrets into the repository.

If CA attachment cannot precede first deployment, explicitly approve the initial
API deployment failing closed, then CA delivery and one API redeployment of the
same approved commit. The web service may become public during initial creation.
The API startup checks schema and queries the user store after CA validation;
therefore a successful API deployment entails ordinary application database
queries. No manual SQL, migrations, bootstrap or grants are authorized. If the
SQL prohibition includes application-generated queries, keep the API stopped
pending separate authorization. Missing schema/permissions are a stop condition,
not permission to repair the database. `/healthz` alone is not a readiness audit.

### Remaining approvals, in order

1. **Publish:** approve the exact prepared commit to the dedicated repository
   branch, bound to the archive and manifest hashes above. No hosted changes.
2. **Create and initially deploy:** after reviewing the live preview and current
   free-hour/bandwidth/build limits, approve only the two named Free services,
   generated API signing secret, existing staging URL delivery, and initial
   deployments. Accept the public web endpoint and possible initial API CA failure.
   No additional spending, existing Redis access, production change or SQL work.
3. **CA delivery and API redeployment:** approve the pinned CA file upload and
   same-commit API redeployment, including normal application startup queries
   against staging only. Keep blocked if database prerequisites are unconfirmed.

Record approver, UTC approval time/expiry, repository commit and live resource
IDs with each scope. No approval is implied by this document. Stop if the preview,
candidate hashes, configuration or cost differs from the authorized scope.

Provider references checked for this review:
[Blueprint semantics](https://render.com/docs/blueprint-spec),
[Blueprint creation and Auto Sync](https://render.com/docs/infrastructure-as-code),
[secret-file delivery](https://render.com/docs/configure-environment-variables).
