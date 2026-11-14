"""Private operator identity schema tests using disposable PostgreSQL only."""

import importlib.util
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import sqlalchemy as sa
import test_storage_lifecycle as lifecycle
from sqlalchemy.exc import DBAPIError

ROOT = Path(__file__).resolve().parents[1]
OWNER = "vervfy_operator_foundation_owner"
SCHEMA = "vervfy_operator"
RUNTIME_ROLES = ("app_runtime", "storage_cleanup_worker", "google_auth_lookup")
TABLES = (
    "operator_identities",
    "operator_credentials",
    "operator_role_assignments",
    "operator_sessions",
    "storage_operator_audit",
)


class OperatorIdentityFoundationTests(unittest.TestCase):
    setUpClass = classmethod(lifecycle.StorageLifecycleTests.setUpClass.__func__)

    @contextmanager
    def owner(self):
        with self.admin.begin() as connection:
            connection.exec_driver_sql(f"SET LOCAL ROLE {OWNER}")
            yield connection

    def add_operator(self, connection, identifier, **fields):
        values = {
            "identifier": identifier,
            "status": fields.pop("status", "active"),
            "suspended_at": fields.pop("suspended_at", None),
            "revoked_at": fields.pop("revoked_at", None),
            "provisioning_method": fields.pop("provisioning_method", "break_glass"),
            "provisioning_reason": fields.pop(
                "provisioning_reason", "synthetic fixture"
            ),
            "provisioning_reference": fields.pop(
                "provisioning_reference", "test-change-001"
            ),
        }
        values.update(fields)
        return connection.execute(
            sa.text("""
            INSERT INTO vervfy_operator.operator_identities(
                normalized_identifier,account_status,suspended_at,revoked_at,
                provisioned_by_operator_id,provisioning_method,
                provisioning_reason,provisioning_reference
            ) VALUES (
                :identifier,:status,:suspended_at,:revoked_at,
                :provisioned_by_operator_id,:provisioning_method,
                :provisioning_reason,:provisioning_reference
            ) RETURNING id
            """),
            {
                "identifier": values["identifier"],
                "status": values["status"],
                "suspended_at": values["suspended_at"],
                "revoked_at": values["revoked_at"],
                "provisioned_by_operator_id": values.get("provisioned_by_operator_id"),
                "provisioning_method": values["provisioning_method"],
                "provisioning_reason": values["provisioning_reason"],
                "provisioning_reference": values["provisioning_reference"],
            },
        ).scalar_one()

    @contextmanager
    def rejected(self, connection, state):
        with (
            self.assertRaises(DBAPIError) as caught,
            connection.begin_nested(),
        ):
            yield
        self.assertEqual(caught.exception.orig.sqlstate, state)

    def test_head_upgrade_and_private_rls_acl_role_graph(self):
        with self.admin.connect() as connection:
            self.assertEqual(
                connection.execute(
                    sa.text("SELECT version_num FROM alembic_version")
                ).scalar_one(),
                "0033_cleanup_activation_gate",
            )
            for table in TABLES:
                policy = connection.execute(
                    sa.text("""
                    SELECT c.relrowsecurity,c.relforcerowsecurity,
                           pg_catalog.has_table_privilege(
                               :owner,c.oid,'SELECT,INSERT,UPDATE,DELETE'
                           ) AS owner_access
                    FROM pg_catalog.pg_class c
                    JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname=:schema AND c.relname=:table
                    """),
                    {"owner": OWNER, "schema": SCHEMA, "table": table},
                ).one()
                self.assertEqual(tuple(policy), (True, True, True))
                for role in RUNTIME_ROLES:
                    self.assertFalse(
                        connection.execute(
                            sa.text("""
                            SELECT pg_catalog.has_schema_privilege(:role,:schema,'USAGE')
                                OR pg_catalog.has_table_privilege(:role,:table,'SELECT')
                            """),
                            {
                                "role": role,
                                "schema": SCHEMA,
                                "table": f"{SCHEMA}.{table}",
                            },
                        ).scalar_one()
                    )

            self.assertFalse(
                connection.execute(
                    sa.text("""
                    SELECT pg_catalog.pg_has_role(
                        'app_runtime',:owner,'USAGE'
                    ) OR pg_catalog.pg_has_role('app_runtime',:owner,'SET')
                    """),
                    {"owner": OWNER},
                ).scalar_one()
            )
            owner_membership = connection.execute(
                sa.text("""
                SELECT inherit_option,set_option,admin_option
                FROM pg_catalog.pg_auth_members
                WHERE roleid=pg_catalog.to_regrole(:owner)
                  AND member=pg_catalog.to_regrole('migration_owner')
                """),
                {"owner": OWNER},
            ).one()
            self.assertEqual(tuple(owner_membership), (False, True, False))
            self.assertEqual(
                connection.execute(
                    sa.text("""
                    SELECT count(*) FROM pg_catalog.pg_auth_members
                    WHERE roleid=pg_catalog.to_regrole(:owner)
                      AND member<>pg_catalog.to_regrole('migration_owner')
                    """),
                    {"owner": OWNER},
                ).scalar_one(),
                0,
            )
            public_execute = connection.execute(
                sa.text("""
                SELECT count(*) FROM pg_catalog.pg_proc p
                JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
                CROSS JOIN LATERAL pg_catalog.aclexplode(p.proacl) a
                WHERE n.nspname=:schema AND a.grantee=0
                  AND a.privilege_type='EXECUTE'
                """),
                {"schema": SCHEMA},
            ).scalar_one()
            self.assertEqual(public_execute, 0)
            public_schema_access = connection.execute(
                sa.text("""
                SELECT count(*) FROM pg_catalog.pg_namespace n
                CROSS JOIN LATERAL pg_catalog.aclexplode(n.nspacl) a
                WHERE n.nspname=:schema AND a.grantee=0
                """),
                {"schema": SCHEMA},
            ).scalar_one()
            self.assertEqual(public_schema_access, 0)
            public_table_access = connection.execute(
                sa.text("""
                SELECT count(*) FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                CROSS JOIN LATERAL pg_catalog.aclexplode(c.relacl) a
                WHERE n.nspname=:schema AND a.grantee=0
                """),
                {"schema": SCHEMA},
            ).scalar_one()
            self.assertEqual(public_table_access, 0)
            private_columns = connection.execute(
                sa.text("""
                SELECT count(*) FROM information_schema.columns
                WHERE table_schema=:schema AND column_name ILIKE '%private_key%'
                """),
                {"schema": SCHEMA},
            ).scalar_one()
            self.assertEqual(private_columns, 0)

    def test_operator_creation_identifier_constraints_and_provisioning_metadata(self):
        with self.owner() as connection:
            operator_id = self.add_operator(connection, "synthetic-operator")
            row = connection.execute(
                sa.text("""
                SELECT normalized_identifier,account_status,provisioning_method,
                       provisioning_reference,provisioning_reason
                FROM vervfy_operator.operator_identities WHERE id=:id
                """),
                {"id": operator_id},
            ).one()
            self.assertEqual(
                tuple(row),
                (
                    "synthetic-operator",
                    "active",
                    "break_glass",
                    "test-change-001",
                    "synthetic fixture",
                ),
            )
            with self.rejected(connection, "23505"):
                self.add_operator(connection, "synthetic-operator")
            with self.rejected(connection, "23514"):
                self.add_operator(connection, "Synthetic-Operator")
            with self.rejected(connection, "23514"):
                self.add_operator(
                    connection,
                    "missing-reference",
                    provisioning_reference=None,
                )

    def test_credentials_are_public_key_only_and_owned_by_an_operator(self):
        credential_id = b"synthetic-credential-id"
        with self.owner() as connection:
            operator_id = self.add_operator(connection, "credential-owner")
            connection.execute(
                sa.text("""
                INSERT INTO vervfy_operator.operator_credentials(
                    credential_id,operator_id,public_key,credential_metadata,
                    signature_counter,backup_eligible,backup_state
                ) VALUES (
                    :credential_id,:operator_id,:public_key,'{"aaguid":"synthetic"}',
                    4,true,true
                )
                """),
                {
                    "credential_id": credential_id,
                    "operator_id": operator_id,
                    "public_key": b"synthetic-public-cose-key",
                },
            )
            with self.rejected(connection, "23503"):
                connection.execute(
                    sa.text("""
                        INSERT INTO vervfy_operator.operator_credentials(
                            credential_id,operator_id,public_key
                        ) VALUES (:credential_id,:operator_id,:key)
                        """),
                    {
                        "credential_id": b"orphaned-credential",
                        "operator_id": uuid.uuid4(),
                        "key": b"synthetic-public-key",
                    },
                )
            with self.rejected(connection, "23514"):
                connection.execute(
                    sa.text("""
                        INSERT INTO vervfy_operator.operator_credentials(
                            credential_id,operator_id,public_key,backup_eligible,
                            backup_state
                        ) VALUES (:credential_id,:operator_id,:key,false,true)
                        """),
                    {
                        "credential_id": b"invalid-backup-state",
                        "operator_id": operator_id,
                        "key": b"synthetic-public-key",
                    },
                )
            with self.rejected(connection, "23514"):
                connection.execute(
                    sa.text("""
                    INSERT INTO vervfy_operator.operator_credentials(
                        credential_id,operator_id,public_key,credential_metadata
                    ) VALUES (
                        :credential_id,:operator_id,:key,'{"private_key":"forbidden"}'
                    )
                    """),
                    {
                        "credential_id": b"forbidden-private-metadata",
                        "operator_id": operator_id,
                        "key": b"synthetic-public-key",
                    },
                )

    def test_role_assignment_revocation_and_explicit_bootstrap_grant(self):
        with self.owner() as connection:
            admin_id = self.add_operator(connection, "granting-admin")
            subject_id = self.add_operator(connection, "role-subject")
            bootstrap_assignment_id = connection.execute(
                sa.text("""
                INSERT INTO vervfy_operator.operator_role_assignments(
                    operator_id,role,reason,bootstrap_reference
                ) VALUES (:admin,'operator_admin','synthetic bootstrap','two-person ticket')
                RETURNING id
                """),
                {"admin": admin_id},
            ).scalar_one()
            extra_operator = self.add_operator(connection, "second-bootstrap")
            with self.rejected(connection, "42501"):
                connection.execute(
                    sa.text("""
                    INSERT INTO vervfy_operator.operator_role_assignments(
                        operator_id,role,reason,bootstrap_reference
                    ) VALUES (:operator,'operator_admin','second bootstrap','forbidden')
                    """),
                    {"operator": extra_operator},
                )
            assignment_id = connection.execute(
                sa.text("""
                INSERT INTO vervfy_operator.operator_role_assignments(
                    operator_id,role,granting_admin_operator_id,reason
                ) VALUES (:subject,'storage_reviewer',:admin,'synthetic grant')
                RETURNING id
                """),
                {"subject": subject_id, "admin": admin_id},
            ).scalar_one()
            with self.rejected(connection, "42501"):
                connection.execute(
                    sa.text("""
                        INSERT INTO vervfy_operator.operator_role_assignments(
                            operator_id,role,granting_admin_operator_id,reason
                        ) VALUES (:subject,'operator_admin',:subject,'self grant')
                        """),
                    {"subject": subject_id},
                )
            with self.rejected(connection, "23505"):
                connection.execute(
                    sa.text("""
                        INSERT INTO vervfy_operator.operator_role_assignments(
                            operator_id,role,granting_admin_operator_id,reason
                        ) VALUES (:subject,'storage_reviewer',:admin,'duplicate')
                        """),
                    {"subject": subject_id, "admin": admin_id},
                )
            connection.execute(
                sa.text("""
                UPDATE vervfy_operator.operator_role_assignments
                SET revoked_at=pg_catalog.clock_timestamp(),revoked_by_operator_id=:admin
                WHERE id=:id
                """),
                {"admin": admin_id, "id": assignment_id},
            )
            connection.execute(
                sa.text("""
                INSERT INTO vervfy_operator.operator_role_assignments(
                    operator_id,role,granting_admin_operator_id,reason
                ) VALUES (:subject,'storage_reviewer',:admin,'replacement grant')
                """),
                {"subject": subject_id, "admin": admin_id},
            )
            active = connection.execute(
                sa.text("""
                SELECT count(*) FROM vervfy_operator.operator_role_assignments
                WHERE operator_id=:id AND role='storage_reviewer' AND revoked_at IS NULL
                """),
                {"id": subject_id},
            ).scalar_one()
            self.assertEqual(active, 1)
            connection.execute(
                sa.text("""
                UPDATE vervfy_operator.operator_role_assignments
                SET revoked_at=pg_catalog.clock_timestamp(),
                    revoked_by_operator_id=:admin
                WHERE id=:assignment
                """),
                {"admin": admin_id, "assignment": bootstrap_assignment_id},
            )
            for reference in ("two-person ticket", "new but unauthorized reference"):
                with self.rejected(connection, "42501"):
                    connection.execute(
                        sa.text("""
                        INSERT INTO vervfy_operator.operator_role_assignments(
                            operator_id,role,reason,bootstrap_reference
                        ) VALUES (:operator,'operator_admin','bootstrap replay',:reference)
                        """),
                        {"operator": extra_operator, "reference": reference},
                    )

    def test_credential_revocation_revokes_sessions_and_is_monotonic(self):
        credential_id = b"credential-revocation-test"
        with self.owner() as connection:
            operator_id = self.add_operator(
                connection, "credential-revocation-operator"
            )
            connection.execute(
                sa.text("""
                INSERT INTO vervfy_operator.operator_credentials(
                    credential_id,operator_id,public_key
                ) VALUES (:credential,:operator,:key)
                """),
                {
                    "credential": credential_id,
                    "operator": operator_id,
                    "key": b"synthetic-public-key",
                },
            )
            session_id = connection.execute(
                sa.text("""
                INSERT INTO vervfy_operator.operator_sessions(
                    operator_id,credential_id,session_token_hash,expires_at
                ) VALUES (
                    :operator,:credential,:token,
                    pg_catalog.clock_timestamp()+interval '10 minutes'
                ) RETURNING id
                """),
                {
                    "operator": operator_id,
                    "credential": credential_id,
                    "token": b"c" * 32,
                },
            ).scalar_one()
            connection.execute(
                sa.text("""
                UPDATE vervfy_operator.operator_credentials
                SET revoked_at=pg_catalog.clock_timestamp()
                WHERE credential_id=:credential
                """),
                {"credential": credential_id},
            )
            self.assertIsNotNone(
                connection.execute(
                    sa.text("""
                    SELECT revoked_at FROM vervfy_operator.operator_sessions
                    WHERE id=:id
                    """),
                    {"id": session_id},
                ).scalar_one()
            )
            with self.rejected(connection, "55000"):
                connection.execute(
                    sa.text("""
                    UPDATE vervfy_operator.operator_credentials
                    SET revoked_at=NULL WHERE credential_id=:credential
                    """),
                    {"credential": credential_id},
                )
            with self.rejected(connection, "55000"):
                connection.execute(
                    sa.text("""
                    UPDATE vervfy_operator.operator_credentials
                    SET public_key=:key WHERE credential_id=:credential
                    """),
                    {"credential": credential_id, "key": b"replacement-key"},
                )

    def test_suspension_revocation_and_independent_session_constraints(self):
        with self.owner() as connection:
            suspended_id = self.add_operator(
                connection,
                "suspended-operator",
                status="suspended",
                suspended_at="2026-01-01T00:00:00Z",
            )
            revoked_id = self.add_operator(
                connection,
                "revoked-operator",
                status="revoked",
                revoked_at="2026-01-01T00:00:00Z",
            )
            active_id = self.add_operator(connection, "session-operator")
            credential_id = b"session-credential"
            for identity, credential in (
                (active_id, credential_id),
                (suspended_id, b"suspended-credential"),
                (revoked_id, b"revoked-credential"),
            ):
                connection.execute(
                    sa.text("""
                INSERT INTO vervfy_operator.operator_credentials(
                    credential_id,operator_id,public_key
                ) VALUES (:credential_id,:operator_id,:key)
                """),
                    {
                        "credential_id": credential,
                        "operator_id": identity,
                        "key": b"synthetic-public-key",
                    },
                )
            token_hash = b"h" * 32
            session_id = connection.execute(
                sa.text("""
                INSERT INTO vervfy_operator.operator_sessions(
                    operator_id,credential_id,session_token_hash,expires_at
                ) VALUES (
                    :operator_id,:credential_id,:token_hash,
                    pg_catalog.clock_timestamp()+interval '10 minutes'
                )
                RETURNING id
                """),
                {
                    "operator_id": active_id,
                    "credential_id": credential_id,
                    "token_hash": token_hash,
                },
            ).scalar_one()
            for identity, credential in (
                (suspended_id, b"suspended-credential"),
                (revoked_id, b"revoked-credential"),
            ):
                with self.rejected(connection, "42501"):
                    connection.execute(
                        sa.text("""
                        INSERT INTO vervfy_operator.operator_sessions(
                            operator_id,credential_id,session_token_hash,expires_at
                        ) VALUES (
                            :operator_id,:credential_id,:token_hash,
                            pg_catalog.clock_timestamp()+interval '10 minutes'
                        )
                        """),
                        {
                            "operator_id": identity,
                            "credential_id": credential,
                            "token_hash": b"x" * 32,
                        },
                    )
            connection.execute(
                sa.text("""
                UPDATE vervfy_operator.operator_identities
                SET account_status='suspended',
                    suspended_at=pg_catalog.clock_timestamp()
                WHERE id=:id
                """),
                {"id": active_id},
            )
            self.assertIsNotNone(
                connection.execute(
                    sa.text("""
                    SELECT revoked_at FROM vervfy_operator.operator_sessions
                    WHERE id=:id
                    """),
                    {"id": session_id},
                ).scalar_one()
            )
            with self.rejected(connection, "55000"):
                connection.execute(
                    sa.text("""
                    UPDATE vervfy_operator.operator_sessions
                    SET revoked_at=NULL WHERE id=:id
                    """),
                    {"id": session_id},
                )
            with self.rejected(connection, "23514"):
                self.add_operator(connection, "invalid-revocation", status="revoked")
            self.assertEqual(
                connection.execute(
                    sa.text("""
                    SELECT count(*) FROM vervfy_operator.operator_identities
                    WHERE id IN (:suspended,:revoked) AND account_status IN ('suspended','revoked')
                    """),
                    {"suspended": suspended_id, "revoked": revoked_id},
                ).scalar_one(),
                2,
            )

    def test_storage_audit_is_append_only_even_for_foundation_owner(self):
        with self.owner() as connection:
            operator_id = self.add_operator(connection, "audit-operator")
            audit_id = connection.execute(
                sa.text("""
                INSERT INTO vervfy_operator.storage_operator_audit(
                    operator_id,action,target_resource_type,target_resource_id,
                    previous_state,resulting_state,reason,request_id
                ) VALUES (
                    :operator_id,'storage.cleanup.inspect','cleanup_job',
                    'synthetic-job','{"state":"manual_review"}'::jsonb,
                    '{"state":"manual_review"}'::jsonb,'synthetic review',:request_id
                ) RETURNING id
                """),
                {"operator_id": operator_id, "request_id": uuid.uuid4()},
            ).scalar_one()
            for statement in (
                (
                    "UPDATE vervfy_operator.storage_operator_audit "
                    "SET reason='rewritten' WHERE id=:id"
                ),
                "DELETE FROM vervfy_operator.storage_operator_audit WHERE id=:id",
            ):
                with self.rejected(connection, "55000"):
                    connection.execute(sa.text(statement), {"id": audit_id})
            with self.rejected(connection, "55000"):
                connection.exec_driver_sql(
                    "TRUNCATE vervfy_operator.storage_operator_audit"
                )
            self.assertEqual(
                connection.execute(
                    sa.text("""
                    SELECT reason FROM vervfy_operator.storage_operator_audit
                    WHERE id=:id
                    """),
                    {"id": audit_id},
                ).scalar_one(),
                "synthetic review",
            )

    def test_runtime_cannot_provision_and_existing_tenant_rls_is_preserved(self):
        for role in RUNTIME_ROLES:
            with self.engines[role].begin() as connection:
                with self.assertRaises(DBAPIError) as denied:
                    connection.execute(
                        sa.text("""
                        INSERT INTO vervfy_operator.operator_identities(
                            normalized_identifier,provisioning_method,
                            provisioning_reason,provisioning_reference
                        ) VALUES ('unauthorized','break_glass','no','test')
                        """)
                    )
                self.assertEqual(denied.exception.orig.sqlstate, "42501")
        with self.engines["app_runtime"].begin() as connection:
            connection.exec_driver_sql("SET LOCAL app.current_user_id='a'")
            self.assertEqual(
                connection.exec_driver_sql("SELECT count(*) FROM tracks").scalar_one(),
                1,
            )
            with self.assertRaises(DBAPIError):
                connection.exec_driver_sql(
                    "SELECT * FROM vervfy_operator.operator_identities"
                )
        with self.engines["app_runtime"].begin() as connection:
            connection.exec_driver_sql("SET LOCAL app.current_user_id='b'")
            self.assertEqual(
                connection.exec_driver_sql("SELECT count(*) FROM tracks").scalar_one(),
                1,
            )

    def test_migration_is_forward_only_and_downgrade_preserves_schema(self):
        spec = importlib.util.spec_from_file_location(
            "operator_foundation_migration",
            ROOT / "alembic/versions/0030_operator_foundation.py",
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        self.assertEqual(migration.revision, "0030_operator_foundation")
        self.assertEqual(migration.down_revision, "0029_cleanup_retry_limits")
        with self.assertRaisesRegex(RuntimeError, "forward-only"):
            migration.downgrade()
        with self.admin.connect() as connection:
            self.assertTrue(
                connection.execute(
                    sa.text("SELECT pg_catalog.to_regclass(:name) IS NOT NULL"),
                    {"name": f"{SCHEMA}.storage_operator_audit"},
                ).scalar_one()
            )
        migration_spec = importlib.util.spec_from_file_location(
            "operator_revocation_migration",
            ROOT / "alembic/versions/0031_operator_revocation_bootstrap_guards.py",
        )
        migration = importlib.util.module_from_spec(migration_spec)
        migration_spec.loader.exec_module(migration)
        self.assertEqual(migration.revision, "0031_operator_revocation")
        self.assertEqual(migration.down_revision, "0030_operator_foundation")
        with self.assertRaisesRegex(RuntimeError, "forward-only"):
            migration.downgrade()


class OperatorBootstrapConcurrencyTests(unittest.TestCase):
    setUpClass = classmethod(lifecycle.StorageLifecycleTests.setUpClass.__func__)

    def test_concurrent_bootstrap_creates_at_most_one_first_administrator(self):
        barrier = threading.Barrier(2)

        def bootstrap(index):
            try:
                with self.admin.begin() as connection:
                    connection.exec_driver_sql(f"SET LOCAL ROLE {OWNER}")
                    operator_id = connection.execute(
                        sa.text("""
                        INSERT INTO vervfy_operator.operator_identities(
                            normalized_identifier,account_status,provisioning_method,
                            provisioning_reason,provisioning_reference
                        ) VALUES (
                            :identifier,'active','break_glass','concurrent synthetic test',
                            'synthetic-concurrency'
                        ) RETURNING id
                        """),
                        {"identifier": f"concurrent-bootstrap-{index}"},
                    ).scalar_one()
                    barrier.wait(timeout=10)
                    connection.execute(
                        sa.text("""
                        INSERT INTO vervfy_operator.operator_role_assignments(
                            operator_id,role,reason,bootstrap_reference
                        ) VALUES (
                            :operator,'operator_admin',
                            'concurrent synthetic bootstrap',:reference
                        )
                        """),
                        {
                            "operator": operator_id,
                            "reference": f"synthetic-reference-{index}",
                        },
                    )
                return None
            except DBAPIError as error:
                return error.orig.sqlstate

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(bootstrap, (1, 2)))

        self.assertEqual(results.count(None), 1, results)
        self.assertEqual(
            sum(result in {"42501", "23505"} for result in results),
            1,
        )
        with self.admin.connect() as connection:
            self.assertTrue(
                connection.execute(
                    sa.text("""
                    SELECT count(*) FROM vervfy_operator.operator_role_assignments
                    WHERE role='operator_admin'
                      AND granting_admin_operator_id IS NULL
                      AND revoked_at IS NULL
                    """)
                ).scalar_one()
                == 1
            )
