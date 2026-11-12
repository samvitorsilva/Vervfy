"""Private Unix-socket PostgreSQL only; reuse the existing isolated role fixture."""

import concurrent.futures
import secrets

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_oauth_postgres import ProviderPostgresTests as _ProviderPostgresTests
from test_passkeys import migration

import passkey_schema as s
import passkeys as p


class PasskeyPostgresTests(_ProviderPostgresTests.__bases__[0]):
    setUpClass = classmethod(_ProviderPostgresTests.setUpClass.__func__)
    sql = _ProviderPostgresTests.sql

    def setUp(self):
        _ProviderPostgresTests.setUp(self)
        self.sql("ALTER DEFAULT PRIVILEGES GRANT ALL ON TABLES TO app_user")
        self.passkey_migration = migration()
        with Operations.context(MigrationContext.configure(self.connection)):
            self.passkey_migration.upgrade()

    def seed_security(self):
        self.sql("RESET ROLE")
        for user in ("a", "b"):
            self.connection.execute(
                s.handles.insert().values(user_id=user, handle=user.encode() * 32)
            )
            self.connection.execute(
                s.credentials.insert().values(
                    id=user,
                    user_id=user,
                    credential_id=user.encode(),
                    public_key=b"fixture-not-used-for-verification",
                    algorithm=-7,
                    sign_count=0,
                    backup_eligible=False,
                    backed_up=False,
                    created_at=1000,
                )
            )
        self.sql("SET LOCAL ROLE app_runtime")

    def test_rls_and_least_privilege(self):
        self.seed_security()
        self.assertEqual(self.sql("SELECT * FROM webauthn_credentials").all(), [])
        self.sql("SELECT set_config('app.current_user_id','a',true)")
        self.assertEqual(
            self.sql("SELECT id FROM webauthn_credentials").scalars().all(), ["a"]
        )
        self.assertEqual(
            self.sql(
                "UPDATE webauthn_credentials SET sign_count=1 WHERE user_id='b'"
            ).rowcount,
            0,
        )
        for statement in (
            "UPDATE webauthn_credentials SET user_id='b' WHERE id='a'",
            "UPDATE webauthn_credentials SET public_key='bad' WHERE id='a'",
            "DELETE FROM webauthn_credentials",
            "INSERT INTO webauthn_handles VALUES ('b',decode(repeat('aa',32),'hex'))",
            "SELECT * FROM account_recovery_codes",
            "INSERT INTO account_recovery_states VALUES ('r','a','s',1,'pending',1,2)",
        ):
            with self.assertRaises(DBAPIError), self.connection.begin_nested():
                self.sql(statement)
        # Cross-tenant intent insertion is rejected even with an explicit user_id.
        with self.assertRaises(DBAPIError), self.connection.begin_nested():
            self.sql(
                "INSERT INTO account_action_intents VALUES ('i','b','s',3,'logout_all','d',1000,1100,NULL)"
            )
        for role in ("google_auth_lookup", "vervfy_identity_lookup", "app_user"):
            self.sql(f"SET LOCAL ROLE {role}")
            with self.assertRaises(DBAPIError), self.connection.begin_nested():
                self.sql("SELECT * FROM webauthn_credentials")
        self.sql("RESET ROLE")
        for table in s.TABLES:
            self.assertEqual(
                self.sql(
                    f"SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='{table.name}'::regclass"
                ).one(),
                (True, True),
            )

    def test_empty_rollback_and_hidden_data_guard(self):
        with Operations.context(MigrationContext.configure(self.connection)):
            self.passkey_migration.downgrade()
            self.passkey_migration.upgrade()
        self.seed_security()
        self.sql("SET LOCAL ROLE migration_owner")
        with (
            self.assertRaisesRegex(RuntimeError, "security data"),
            self.connection.begin_nested(),
            Operations.context(MigrationContext.configure(self.connection)),
        ):
            self.passkey_migration.downgrade()
        self.assertEqual(self.sql("SELECT * FROM webauthn_credentials").all(), [])
        self.sql("RESET ROLE")
        self.assertEqual(
            self.sql(
                "SELECT password_hash,session_version FROM users ORDER BY id"
            ).all(),
            [("existing-hash", 7), ("other-hash", 3)],
        )
        self.assertEqual(
            self.sql("SELECT count(*) FROM webauthn_credentials").scalar(), 2
        )

    def test_composite_ownership_and_delete_cascade(self):
        self.seed_security()
        self.sql("RESET ROLE")
        self.connection.execute(
            s.intents.insert().values(
                id="i",
                user_id="a",
                session_binding="s",
                session_version=7,
                action="logout_all",
                payload_digest="a" * 64,
                created_at=1000,
                expires_at=1100,
            )
        )
        with self.assertRaises(DBAPIError), self.connection.begin_nested():
            self.connection.execute(
                s.proofs.insert().values(
                    id="p",
                    user_id="a",
                    intent_id="i",
                    credential_id="b",
                    verified_at=1000,
                    expires_at=1100,
                )
            )
        self.sql("DELETE FROM library WHERE user_id='a'")
        self.sql("DELETE FROM users WHERE id='a'")
        self.assertEqual(
            self.sql("SELECT user_id FROM webauthn_credentials").scalars().all(), ["b"]
        )
        self.assertEqual(
            self.sql("SELECT count(*) FROM account_action_intents").scalar(), 0
        )

    def test_concurrent_proof_consumption_and_rollback(self):
        # Separate committed schema inside this test's private cluster, never app data.
        schema_name = "race_" + secrets.token_hex(8)
        with self.engine.begin() as conn:
            conn.exec_driver_sql(
                f"CREATE SCHEMA {schema_name} AUTHORIZATION migration_owner"
            )
            conn.exec_driver_sql(f"SET LOCAL search_path TO {schema_name}")
            conn.exec_driver_sql("SET LOCAL ROLE migration_owner")
            conn.exec_driver_sql(
                "CREATE TABLE users(id VARCHAR(32) PRIMARY KEY,session_version INTEGER NOT NULL)"
            )
            conn.exec_driver_sql("INSERT INTO users VALUES ('a',1)")
            conn.exec_driver_sql(
                "GRANT USAGE ON SCHEMA " + schema_name + " TO app_runtime"
            )
            conn.exec_driver_sql("GRANT SELECT,UPDATE ON users TO app_runtime")
            with Operations.context(MigrationContext.configure(conn)):
                self.passkey_migration.upgrade()
            conn.exec_driver_sql("SELECT set_config('app.current_user_id','a',true)")
            conn.execute(s.handles.insert().values(user_id="a", handle=b"a" * 32))
            conn.execute(
                s.credentials.insert().values(
                    id="c",
                    user_id="a",
                    credential_id=b"c",
                    public_key=b"fixture",
                    algorithm=-7,
                    sign_count=0,
                    backup_eligible=False,
                    backed_up=False,
                    created_at=1000,
                )
            )
            binding = p.Binding("a", "session", 1, "logout_all")
            conn.execute(
                s.intents.insert().values(
                    id="i",
                    **binding.record(),
                    payload_digest="a" * 64,
                    created_at=1000,
                    expires_at=1100,
                )
            )
            conn.execute(
                s.proofs.insert().values(
                    id="p",
                    user_id="a",
                    intent_id="i",
                    credential_id="c",
                    verified_at=1000,
                    expires_at=1100,
                )
            )

        def consume(fail=False):
            try:
                with (
                    Session(self.engine, info={"tenant_id": "a"}) as session,
                    session.begin(),
                ):
                    session.execute(sa.text("SET LOCAL search_path TO " + schema_name))
                    session.execute(sa.text("SET LOCAL ROLE app_runtime"))
                    session.execute(
                        sa.text("SELECT set_config('app.current_user_id','a',true)")
                    )
                    p.consume_proof(session, binding, "i", "p", "a" * 64, now=1000)
                    if fail:
                        raise RuntimeError("rollback")
                return True
            except p.PasskeyError:
                return False

        try:
            with self.assertRaisesRegex(RuntimeError, "rollback"):
                consume(True)
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(lambda _: consume(), range(4)))
            self.assertEqual(sum(results), 1)
        finally:
            with self.engine.begin() as conn:
                conn.exec_driver_sql(f"DROP SCHEMA {schema_name} CASCADE")
