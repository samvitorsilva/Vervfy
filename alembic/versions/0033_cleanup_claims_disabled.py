"""Disable cleanup claims until physical deletion receives separate approval."""

import sqlalchemy as sa

from alembic import op

revision = "0033_cleanup_claims_disabled"
down_revision = "0032_auth_sessions"
branch_labels = None
depends_on = None

OWNER = "vervfy_storage_lifecycle_owner"
EXECUTOR = "vervfy_storage_cleanup"
WORKER = "storage_cleanup_worker"
APP_RUNTIME = "app_runtime"


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name != "postgresql":
        return

    schema = bind.execute(
        sa.text("SELECT current_schema()")
    ).scalar_one()

    if schema != "public":
        raise RuntimeError("0033 requires the public application schema")

    # Verify all expected roles exist.
    roles = bind.execute(
        sa.text("""
            SELECT rolname
            FROM pg_catalog.pg_roles
            WHERE rolname IN (
                :owner, :executor, :worker, :app_runtime
            )
        """),
        {
            "owner": OWNER,
            "executor": EXECUTOR,
            "worker": WORKER,
            "app_runtime": APP_RUNTIME,
        },
    ).scalars().all()

    if set(roles) != {OWNER, EXECUTOR, WORKER, APP_RUNTIME}:
        raise RuntimeError("0033: required security roles are missing")

    # Only the lifecycle owner may retain SET/ownership authority.
    can_set_owner = bind.execute(
        sa.text("""
            SELECT pg_catalog.pg_has_role(
                current_user, :owner, 'SET'
            )
        """),
        {"owner": OWNER},
    ).scalar_one()

    if not can_set_owner:
        raise RuntimeError(
            "0033: migration role cannot SET ROLE to lifecycle owner"
        )

    # Execute the revoke as the function owner.
    op.execute(f"SET LOCAL ROLE {OWNER}")

    op.execute("""
        REVOKE ALL ON FUNCTION
            vervfy_storage.claim_next_cleanup()
        FROM PUBLIC,
             vervfy_storage_cleanup,
             storage_cleanup_worker,
             app_runtime
    """)

    op.execute("RESET ROLE")

    # Verify effective permissions, including inherited membership.
    result = bind.execute(sa.text("""
        SELECT
            has_function_privilege(
                'vervfy_storage_lifecycle_owner',
                'vervfy_storage.claim_next_cleanup()',
                'EXECUTE'
            ) AS owner_can_claim,

            has_function_privilege(
                'vervfy_storage_cleanup',
                'vervfy_storage.claim_next_cleanup()',
                'EXECUTE'
            ) AS executor_can_claim,

            has_function_privilege(
                'storage_cleanup_worker',
                'vervfy_storage.claim_next_cleanup()',
                'EXECUTE'
            ) AS worker_can_claim,

            has_function_privilege(
                'app_runtime',
                'vervfy_storage.claim_next_cleanup()',
                'EXECUTE'
            ) AS app_can_claim
    """)).one()

    if (
        not result.owner_can_claim
        or result.executor_can_claim
        or result.worker_can_claim
        or result.app_can_claim
    ):
        raise RuntimeError(
            "0033 failed: unexpected effective cleanup-claim privileges"
        )

    # Reject any remaining direct EXECUTE grants to other roles.
    unexpected = bind.execute(sa.text("""
        SELECT r.rolname
        FROM pg_catalog.pg_proc p
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                p.proacl,
                pg_catalog.acldefault('f', p.proowner)
            )
        ) a
        LEFT JOIN pg_catalog.pg_roles r ON r.oid = a.grantee
        WHERE p.oid = pg_catalog.to_regprocedure(
            'vervfy_storage.claim_next_cleanup()'
        )
          AND a.privilege_type = 'EXECUTE'
          AND a.grantee <> p.proowner
    """)).scalars().all()

    if unexpected:
        raise RuntimeError(
            "0033 failed: unexpected direct cleanup-claim grants remain"
        )


def downgrade() -> None:
    raise RuntimeError(
        "0033 is forward-only; cleanup claims require a separately "
        "reviewed authorization before being restored"
    )
