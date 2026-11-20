# Local proxy security release

Scope: auth.py client identity, server.py early validation and exact slash matching,
render.yaml startup defaults, focused synthetic tests and proxy documentation.
No audit signing endpoint, storage changes, secrets or unrelated workspace edits.
Base: 806f3b6d21a17a1e491ca54b763b504d5f953b43 (verified GitHub commit/tree;
Render last reported this commit live). Do not apply the complete Blueprint to production: unrelated
baseline settings may differ from the live configuration.

## Startup and environment contract

Required command for this application-owned resolver:

```
uvicorn server:app --host 0.0.0.0 --port "$PORT" --no-access-log --no-proxy-headers
```

PORT is supplied by the host. Explicit --no-proxy-headers must survive wrappers
and process managers; no outer middleware may rewrite the ASGI client address.
Do not rely on UVICORN_PROXY_HEADERS or FORWARDED_ALLOW_IPS defaults.

Safe initial configuration (no assumed proxy topology):

```
VERVFY_ENVIRONMENT=production
VERVFY_HTTPS_ONLY=1
VERVFY_COOKIE_SAME_SITE=lax
VERVFY_TRUSTED_PROXY_HOPS=0
```

Leave VERVFY_TRUSTED_PROXY_CIDRS unset while forwarding is disabled. This uses
socket-peer rate-limit identities and can aggregate users behind a proxy. Only
set hops 1..32 and precise CIDRs after verifying every ingress route, XFF append/
overwrite behavior and each selected intermediary. Missing/invalid trust falls
back to the peer; it does not prove a correct deployment. Never assume private
address ranges or Render's name establish trust.

Preserve existing VERVFY_SECRET_KEY, database and Redis settings in their current
secret boundary. Do not copy them into artifacts or rotate the session key as
part of this change. Existing application startup dependencies remain required.
OAuth, when enabled, needs its existing validated HTTPS GOOGLE_REDIRECT_URI and
frontend origin configuration; do not derive them from forwarded headers.

## HTTPS and compatibility

TLS termination means the internal ASGI scheme stays HTTP. Secure session cookies
and HSTS use explicit configuration; the application does not enforce edge HTTP
redirects. External HTTPS, HTTP-to-HTTPS enforcement, alternate hostnames, outer
middleware and browser cookie behavior must be verified separately on Render.
Trailing-slash variants now return 404 without redirects or POST body replay;
clients and health checks must use canonical routes (/healthz, not /healthz/).

## Validation and artifacts

Run focused tests only with synthetic credentials, an in-memory SQLite database,
no inherited service configuration and MockTransport/ASGITransport. Set
VERVFY_HTTPS_ONLY=1 before importing the app so session middleware captures the
secure-cookie setting at startup. See the
external artifact directory's tests.log and manifest.json for exact results,
commit identities and artifact SHA-256. Test credentials are not production keys.
The slash test uses the existing protected upload route rather than depending on
an unrelated administrative signing endpoint.

## Rollback

The release and rollback patches are exact inverses. The local rollback branch
reverts the release commit and must have a tree identical to the local base.
This proves exact restoration of the production source tree at 806f3b6 only;
Render retained-artifact and configuration restoration remain unverified.
Before any future deployment, capture the verified live commit, exact start
command, relevant environment presence/values (exclude secrets), health check,
scaling/autodeploy state and restore owner in an approved private record.
Rollback code, startup command and proxy environment together using that record;
never invent a live baseline from the local base or Blueprint. Preserve secret
values in place. Reverting the resolver can restore its earlier spoofing weakness.
Forwarding hops=0 with --no-proxy-headers is a containment option, with shared-IP
rate-limit impact, not restoration of per-client limits.

No production actions, push, deployment or topology discovery are included here.

GitHub acquisition: git transport DNS was unavailable. GitHub API commit/tree and
missing blobs were imported with exact Git SHA checks in an isolated repository.
The production commit is a shallow history boundary; no parent history was fetched.
Original local branches and the dirty source workspace were preserved.
