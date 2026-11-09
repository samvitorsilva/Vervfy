"""Bound cleanup claims; preserve exhausted obligations for manual review."""

import sqlalchemy as sa

from alembic import op

revision = "0029_cleanup_retry_limits"
down_revision = "0028_storage_cleanup_leases"
branch_labels = None
depends_on = None

OWNER = "vervfy_storage_lifecycle_owner"
EXECUTOR = "vervfy_storage_cleanup"


def _function(signature: str, body: str) -> None:
    bind = op.get_bind()
    name = "vervfy_storage." + signature
    op.execute(body)
    op.execute(f"REVOKE ALL ON FUNCTION {name} FROM PUBLIC")
    for role in bind.execute(
        sa.text("""
        SELECT DISTINCT r.rolname FROM pg_catalog.pg_proc p
        CROSS JOIN LATERAL pg_catalog.aclexplode(p.proacl) a
        JOIN pg_catalog.pg_roles r ON r.oid=a.grantee
        WHERE p.oid=pg_catalog.to_regprocedure(:name) AND r.rolname<>current_user
        """),
        {"name": name},
    ).scalars():
        op.execute(
            f"REVOKE ALL ON FUNCTION {name} FROM "
            f"{bind.dialect.identifier_preparer.quote(role)}"
        )
    op.execute(f"GRANT EXECUTE ON FUNCTION {name} TO {EXECUTOR}")
    op.execute(f"ALTER FUNCTION {name} OWNER TO {OWNER}")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    if bind.execute(sa.text("SELECT current_schema()")).scalar_one() != "public":
        raise RuntimeError("0029 requires the reviewed public application schema")
    op.execute("""
        ALTER TABLE vervfy_storage.cleanup_jobs
        DROP CONSTRAINT cleanup_jobs_state_check,
        ADD CONSTRAINT cleanup_jobs_state_check
            CHECK(state IN ('pending','held','claimed','done','manual_review')),
        ADD COLUMN exhaustion_reason text
            CHECK(exhaustion_reason IN ('attempt_limit_provider_failure',
                  'attempt_limit_lease_expired','attempt_limit_reached'))
    """)
    op.execute(f"GRANT CREATE ON SCHEMA vervfy_storage TO {OWNER}")
    op.execute(f"SET LOCAL ROLE {OWNER}")
    _function(
        "claim_next_cleanup()",
        """
        CREATE OR REPLACE FUNCTION vervfy_storage.claim_next_cleanup()
        RETURNS TABLE(object_id uuid,object_path text,claim_token uuid)
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp AS $$
        DECLARE candidate uuid; obj vervfy_storage.objects%ROWTYPE;
                job vervfy_storage.cleanup_jobs%ROWTYPE;
                v_object_id uuid; v_path text; v_token uuid;
        BEGIN
            FOR candidate IN
                SELECT j.object_id FROM vervfy_storage.cleanup_jobs AS j
                WHERE (j.state='pending' AND j.available_at<=pg_catalog.clock_timestamp())
                   OR (j.state='claimed' AND j.lease_until<=pg_catalog.clock_timestamp())
                ORDER BY j.available_at,j.object_id
                LIMIT 64
            LOOP
                -- Match reference triggers' object-before-outbox lock order.
                SELECT * INTO obj FROM vervfy_storage.objects
                    WHERE id=candidate FOR UPDATE SKIP LOCKED;
                IF NOT FOUND THEN CONTINUE; END IF;
                SELECT * INTO job FROM vervfy_storage.cleanup_jobs AS cleanup_jobs
                    WHERE cleanup_jobs.object_id=candidate FOR UPDATE SKIP LOCKED;
                IF NOT FOUND OR NOT (
                    (job.state='pending' AND job.available_at<=pg_catalog.clock_timestamp())
                    OR (job.state='claimed' AND job.lease_until<=pg_catalog.clock_timestamp())
                ) THEN CONTINUE; END IF;

                -- Exhausted leases/pending retries must never issue a ninth token.
                IF job.attempts>=8 THEN
                    UPDATE vervfy_storage.cleanup_jobs
                    SET state='manual_review',claim_token=NULL,lease_until=NULL,
                        exhaustion_reason=CASE WHEN job.state='claimed'
                            THEN 'attempt_limit_lease_expired'
                            ELSE 'attempt_limit_reached' END
                    WHERE cleanup_jobs.object_id=candidate;
                    CONTINUE;
                END IF;

                IF obj.classification<>'managed' OR NOT obj.upload_verified
                   OR obj.state NOT IN ('ready','live','retired','deleting') THEN
                    UPDATE vervfy_storage.cleanup_jobs
                    SET state='held',claim_token=NULL,lease_until=NULL,
                        error_code='unsafe_object_state'
                    WHERE cleanup_jobs.object_id=candidate;
                    CONTINUE;
                END IF;
                IF vervfy_storage._has_references(obj.path) THEN
                    UPDATE vervfy_storage.cleanup_jobs
                    SET state='pending',available_at=pg_catalog.clock_timestamp()+interval '60 seconds',
                        claim_token=NULL,lease_until=NULL,error_code='referenced'
                    WHERE cleanup_jobs.object_id=candidate;
                    CONTINUE;
                END IF;

                v_token:=pg_catalog.gen_random_uuid();
                UPDATE vervfy_storage.objects SET state='deleting'
                    WHERE id=candidate;
                UPDATE vervfy_storage.cleanup_jobs
                SET state='claimed',attempts=attempts+1,claim_token=v_token,
                    lease_until=pg_catalog.clock_timestamp()+interval '60 seconds',
                    error_code=job.error_code
                WHERE cleanup_jobs.object_id=candidate;
                v_object_id:=candidate;
                v_path:=obj.path;
                RETURN QUERY SELECT v_object_id,v_path,v_token;
                RETURN;
            END LOOP;
        END $$
        """,
    )
    _function(
        "retry_cleanup(uuid,uuid,text)",
        """
        CREATE OR REPLACE FUNCTION vervfy_storage.retry_cleanup(
            p_object uuid,p_token uuid,p_error_code text
        ) RETURNS boolean LANGUAGE plpgsql VOLATILE SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp AS $$
        DECLARE obj vervfy_storage.objects%ROWTYPE;
                job vervfy_storage.cleanup_jobs%ROWTYPE;
                delay_seconds integer;
        BEGIN
            IF p_error_code IS NULL OR p_error_code NOT IN (
                'storage_unavailable','storage_timeout','storage_ambiguous',
                'storage_rejected','storage_unknown'
            ) THEN
                RAISE EXCEPTION 'Invalid cleanup failure code';
            END IF;
            SELECT * INTO obj FROM vervfy_storage.objects
                WHERE id=p_object FOR UPDATE;
            IF NOT FOUND THEN RETURN false; END IF;
            SELECT * INTO job FROM vervfy_storage.cleanup_jobs
                WHERE object_id=p_object FOR UPDATE;
            IF NOT FOUND OR job.state<>'claimed' OR job.claim_token IS DISTINCT FROM p_token
               OR job.lease_until<=pg_catalog.clock_timestamp()
               OR obj.state<>'deleting' THEN
                RETURN false;
            END IF;
            delay_seconds:=LEAST(3600,5*pg_catalog.power(2,LEAST(job.attempts-1,10))::integer);
            UPDATE vervfy_storage.cleanup_jobs
            SET state=CASE WHEN job.attempts>=8 THEN 'manual_review' ELSE 'pending' END,
                exhaustion_reason=CASE WHEN job.attempts>=8
                    THEN 'attempt_limit_provider_failure' ELSE NULL END,
                available_at=pg_catalog.clock_timestamp()
                    +pg_catalog.make_interval(secs=>delay_seconds),
                claim_token=NULL,lease_until=NULL,error_code=p_error_code
            WHERE object_id=p_object;
            RETURN true;
        END $$
        """,
    )
    op.execute("RESET ROLE")
    op.execute("REVOKE CREATE ON SCHEMA vervfy_storage FROM " + OWNER)


def downgrade() -> None:
    raise RuntimeError(
        "0029 is forward-only: preserve retry limits and manual review obligations"
    )
