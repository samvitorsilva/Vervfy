# Client IP trust boundary

`auth.client_ip` defaults to the canonical socket peer, or the fixed `unknown`
identity when no valid peer is available. Untrusted headers cannot select a
rate-limit key. IPv4-mapped IPv6 addresses normalize to IPv4.

Forwarded-header mode requires BOTH `VERVFY_TRUSTED_PROXY_HOPS` (1–32) and
`VERVFY_TRUSTED_PROXY_CIDRS` (comma-separated exact IPs/CIDRs). There is no
default trusted proxy range. Missing/invalid configuration or universal trust
ranges fall back to the peer; this can aggregate users behind a proxy, so it is
not evidence of correct production configuration. Missing XFF also uses peer.

The socket peer and every intermediary in the selected right-hand suffix must
belong to the allowlist. The selected client is the Nth address from the right,
where N counts the socket proxy and N−1 intermediary addresses. No proxy count
is inferred from Render's brand, private address ranges, or existing examples.

From a trusted peer, duplicate XFF headers, empty/invalid addresses, host:port,
scoped IPv6, controls, insufficient chains and oversized input return generic
HTTP 400. All entries are validated, including unused attacker-supplied prefixes.
Untrusted peers' forwarded headers are ignored entirely. Other forwarding headers
do not participate in rate-limit identity.

## Operator decisions before release

- Establish actual public, frontend-proxy and private-network ingress paths and
  which proxies append/overwrite XFF. Confirm the client cannot control the
  selected suffix. Provide precise trusted proxy IPs/CIDRs and verified hop count;
  avoid broad private-network trust that includes untrusted workloads.
- Choose exactly one resolver. This application mode requires the original socket
  peer: configure Uvicorn not to rewrite XFF before the app (for example, separately
  approved `--no-proxy-headers`). Review effects on HTTPS/scheme handling before
  changing that flag. An already spoofed ASGI peer cannot be repaired here.
- This patch's supported deployment uses the application as the single resolver.
  Hops 0 disables forwarding and uses the original socket peer. Do not combine
  this deployment with an upstream IP resolver or wildcard Uvicorn proxy trust.
- Existing render.yaml's hop-count example does not establish a trusted topology.
  No live Render environment/start command was changed by this patch. Redis, tracing,
  audit-signing activation and deployment approvals remain independent.

Validation: 27 new offline request-resolution regression cases passed. No network,
production requests, migrations, deployment or environment changes performed.
This patch is local and is not included in previously recorded audit-release hashes.

## Integration follow-up

The local Render template now supplies explicit `--no-proxy-headers` and defaults
application hops to 0 (disabled, not an assumed topology). The actual Render
Dashboard start command is unchanged. To adopt this patch, the operator must
separately approve adding `--no-proxy-headers` to that command, e.g.:

```
uvicorn server:app --host 0.0.0.0 --port $PORT --no-proxy-headers
```

Do not apply the entire local Blueprint: other settings differ from production.
The explicit CLI flag overrides `UVICORN_PROXY_HEADERS=true` and prevents wildcard
`FORWARDED_ALLOW_IPS` from rewriting peers. The application cannot recover the
socket peer if an old startup command already rewrote it. Release with that old
command is unsupported; verify command/outer ASGI middleware before deployment.

The HTTP middleware resolves/caches identity before any limiter, returns generic
no-store HTTP 400 for malformed trusted headers, and shares that identity with
authentication. Untrusted headers and absent trust retain validated-peer fallback.
Production secure-cookie and OAuth redirect configuration remains independent of
forwarded scheme headers; review any external scheme-dependent middleware before
disabling Uvicorn's forwarded-protocol handling.

Ten focused integration cases passed for early HTTP 400 on login/register/API/
OAuth paths, no limiter access on rejected requests, single resolution, CLI flag
precedence, session-CSRF continuity and unauthenticated 401. All sessions/requests
were synthetic and local. No production configuration, push or deployment occurred.
