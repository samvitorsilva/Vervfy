# Staging plan with occupied Free Key Value slot

**Status: planning only; deployment is not authorized.** The owner reports
an unrelated active Free Redis/Key Value service in the Render workspace.
It must not be modified, deleted, connected to, or shared with staging.
The prior three-service approval package is superseded.

## Recommendation

For a short, controlled password-only staging phase, use one API process with
`REDIS_URL` unset, Google OAuth disabled, and asynchronous uploads disabled.
The current working proposal defines only the staging API and web services;
it creates no Redis or database. The candidate code provides process-local
session and throttle stores. This is isolated from the existing Redis and
requires no new Redis service or Redis credentials. It is suitable only for
limited staging tests, not a production-equivalent multi-process or OAuth test.
Verify effective settings and worker count before any future deployment.

Sessions and rate limits are lost on restart, redeploy or spin-down; users
must sign in again and rate limits reset. Concurrent workers or replicas have
independent state, so do not scale out. Render Free web services spin down
after 15 minutes of inactivity and may restart; free hours, bandwidth and
build quotas are shared and excess usage can incur charges. Confirm current
usage and billing controls before any future approval. See
[Render Free](https://render.com/docs/free).

Google OAuth requires its Redis-backed one-time transaction store; it remains
disabled. Full OAuth, restart-resilient session, multi-worker and distributed
rate-limit verification are blocked until a separate isolated Redis-compatible
service is reviewed and approved.

## Alternatives

- **Local Redis:** useful for local-only tests with a local API. Render's
  localhost is its own container, not the operator's machine. A tunnel or
  port forward would introduce remote access, availability and security
  dependencies, so it is not recommended as hosted staging infrastructure.
- **Separately hosted Redis-compatible service:** a dedicated free tier such
  as [Upstash Redis](https://upstash.com/pricing/redis) may support hosted
  OAuth tests without using the occupied Render slot. It is conditional, not
  a guaranteed zero-cost solution: verify current limits, billing, regional
  availability, TLS/certificate validation, Redis protocol and command
  compatibility, egress, credential handling, data isolation and behavior on
  quota exhaustion before choosing it. It introduces a third-party data
  processor and network dependency. Never reuse production or existing Redis.
- **Redis inside the API container:** avoids a separate service but couples
  two processes and their lifecycle, remains ephemeral, and adds operational
  and security complexity. The current proposal does not implement this; it
  is not recommended for a trustworthy hosted OAuth test.

## Isolation and future deployment gate

Keep the existing Supabase PostgreSQL 17 staging project and its approved
restricted runtime identity and TLS verification; do not use the production
database, credentials, or storage. Render environments in the same workspace
and region do not automatically provide network isolation; verify the change
preview and effective configuration, and avoid attaching production resources.
See [Render private networking](https://render.com/docs/private-network).

The working two-service proposal differs from the previously archived
three-service candidate and its approval package. Before future deployment,
freeze and independently verify the exact source, archive and manifest hashes;
review all configuration, isolation, costs and hostnames; obtain new approval
for that exact candidate. This document grants no authorization to provision,
change credentials, run SQL, publish or deploy.
