# Explicit storage namespace initialization

This procedure changes database metadata only. It never connects to storage,
creates buckets, lists objects, reads object bytes, or enables physical deletion.
It is implemented by `storage_namespace.initialize_namespace`; startup never
calls it. Local verification uses synthetic bindings on disposable PostgreSQL.
Hosted execution requires separate approval and verified endpoint identity.

Before any hosted execution, approve the exact database, storage endpoint,
private bucket, environment and UUID together. Confirm the bucket belongs to
that environment and is isolated from production/staging peers. Storage access
and credentials are a separate operator verification; this function cannot prove
bucket ownership. Freeze those values in a reviewed binding record, and approve
its hash with the release artifact. Do not generate a new UUID on retries.

On the reviewed Supabase PG17.11 staging project, `postgres` has BYPASSRLS but
is not superuser. The initializer also needs `USAGE` on `vervfy_storage`,
`SELECT` on `public.alembic_version`, and `SELECT`, `INSERT`, and `MAINTAIN` on
`vervfy_storage.namespaces`. `MAINTAIN` is required for its `EXCLUSIVE` table
lock; `INSERT` alone does not permit that lock. The guarded
`staging-namespace-bootstrap-grant.sql` grants only these temporary capabilities
to `postgres` after revision 0027. Run the matching revoke script immediately
after initialization, including after a failed attempt. Never grant BYPASSRLS
or permanent namespace write privileges to an application role.

The migration runner must target `0027_storage_lifecycle`. Keep 0028 unapplied.
After metadata/role postflight and the approved temporary grant, use the
authorized operator executor to connect to database `postgres` through the
verified Supabase session pooler with `sslmode=verify-full`. Inject credentials
through the secret store. Within one transaction call:

```python
from uuid import UUID
from storage_namespace import NamespaceBinding, initialize_namespace

# approved_engine and reviewed_record are supplied by the approved operator
# executor, after endpoint, role and record-hash verification.
binding = NamespaceBinding(
    UUID(reviewed_record["namespace_id"]),
    reviewed_record["environment"],
    reviewed_record["endpoint"],
    reviewed_record["bucket"],
)
with approved_engine.begin() as connection:
    initialize_namespace(connection, binding)
```

Commit only after successful return. A savepoint rolls back failed attempts,
even when the executor catches an exception. An outer transaction rollback
removes a new binding. The table lock serializes simultaneous initializations;
identical retries return successfully without UPDATE. A changed UUID, environment,
endpoint or bucket fails without changing the existing binding. Never delete,
update, truncate, disable triggers, or bypass the immutable namespace guard to
repair a mismatch; stop for reviewed recovery.

Read back exactly one row with the approved tuple and
`physical_cleanup_enabled=false`. Confirm `public.alembic_version` is exactly
`0027_storage_lifecycle` and the 0028 routines are absent. Then configure
`VERVFY_STORAGE_NAMESPACE_ID`, `VERVFY_ENVIRONMENT`, `SUPABASE_URL` and
`SUPABASE_BUCKET` to match. Validate application startup with explicit
`--lifespan on` before separately approving storage smoke tests. Keep the cleanup
worker stopped and physical deletion disabled.

Revoke the temporary privileges with
`docs/staging-namespace-bootstrap-revoke.sql` as
`vervfy_oauth_staging_user`. Confirm `postgres` no longer has private-schema
USAGE, namespace SELECT/INSERT/MAINTAIN, or `alembic_version` SELECT; rerun the
read-only postflight.
