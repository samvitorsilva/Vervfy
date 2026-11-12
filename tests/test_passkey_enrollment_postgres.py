"""Enrollment migration and races on private disposable PostgreSQL/Valkey."""

import concurrent.futures
import secrets
import unittest
from unittest.mock import Mock

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.orm import Session
from test_oauth_postgres import ProviderPostgresTests as _ProviderFixture
from test_passkey_enrollment import migration28, registration
from test_passkeys import migration
from test_passkeys import redis_client as _redis_client

import auth
import passkey_enrollment as e
import passkey_schema as s
import passkeys as p
from db import ProviderIdentity, User
from google_oauth import GoogleOAuthService, RedisOAuthTransactionStore

redis_client = _redis_client


@pytest.fixture(scope="module")
def postgres():
    # Reuse infrastructure setup without collecting its unrelated unittest methods.
    class Fixture(unittest.TestCase):
        setUpClass = classmethod(_ProviderFixture.setUpClass.__func__)

    Fixture.setUpClass()
    try:
        yield Fixture.engine
    finally:
        Fixture.doClassCleanups()


@pytest.fixture
def pg(postgres):
    name = "enroll_" + secrets.token_hex(8)
    with postgres.begin() as conn:
        conn.exec_driver_sql(f"CREATE SCHEMA {name} AUTHORIZATION migration_owner")
        conn.exec_driver_sql(f"SET LOCAL search_path TO {name}")
        conn.exec_driver_sql("SET LOCAL ROLE migration_owner")
        User.__table__.create(conn)
        ProviderIdentity.__table__.create(conn)
        conn.execute(
            User.__table__.insert(),
            [
                {
                    "id": user,
                    "username": user,
                    "username_key": user,
                    "session_version": 1,
                    "created_at": 1000,
                }
                for user in ("a", "b")
            ],
        )
        conn.exec_driver_sql(
            "ALTER TABLE provider_identities ENABLE ROW LEVEL SECURITY"
        )
        conn.exec_driver_sql("ALTER TABLE provider_identities FORCE ROW LEVEL SECURITY")
        conn.exec_driver_sql(
            "CREATE POLICY identity_tenant ON provider_identities USING (user_id=current_setting('app.current_user_id',true)) WITH CHECK (user_id=current_setting('app.current_user_id',true))"
        )
        conn.exec_driver_sql(
            "GRANT SELECT,INSERT,DELETE ON provider_identities TO app_runtime"
        )
        conn.exec_driver_sql(
            "GRANT USAGE ON SCHEMA "
            + name
            + " TO app_runtime, app_user, google_auth_lookup"
        )
        conn.exec_driver_sql("GRANT SELECT, INSERT, UPDATE ON users TO app_runtime")
        conn.exec_driver_sql("ALTER DEFAULT PRIVILEGES GRANT ALL ON TABLES TO app_user")
        with Operations.context(MigrationContext.configure(conn)):
            migration().upgrade()
            migration28().upgrade()
    try:
        yield postgres, name
    finally:
        with postgres.begin() as conn:
            conn.exec_driver_sql(f"DROP SCHEMA {name} CASCADE")


def scope(session, name, user="a", role="app_runtime"):
    session.execute(sa.text(f"SET LOCAL search_path TO {name}"))
    session.execute(sa.text(f"SET LOCAL ROLE {role}"))
    session.execute(
        sa.text("SELECT set_config('app.current_user_id',:user,true)"), {"user": user}
    )


def test_rls_grants_and_empty_downgrade(pg):
    engine, name = pg
    with engine.begin() as conn:
        conn.exec_driver_sql(f"SET LOCAL search_path TO {name}")
        conn.exec_driver_sql("SET LOCAL ROLE migration_owner")
        with Operations.context(MigrationContext.configure(conn)):
            migration28().downgrade()
            migration28().upgrade()
    with Session(engine, info={"tenant_id": "a"}) as session, session.begin():
        scope(session, name)
        binding = p.Binding("a", "session", 1, "passkey_add")
        grant = e._grant(session, binding, "password", 1000)
        for statement in (
            "UPDATE webauthn_enrollments SET user_id='b'",
            "UPDATE webauthn_enrollments SET expires_at=9999",
            "DELETE FROM webauthn_enrollments",
            "UPDATE webauthn_credentials SET public_key='bad'",
            "UPDATE account_recovery_states SET status='completed'",
            "INSERT INTO webauthn_handles VALUES ('b',decode(repeat('ab',32),'hex'))",
        ):
            with pytest.raises(sa.exc.DBAPIError), session.begin_nested():
                session.execute(sa.text(statement))
        scope(session, name, "b")
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(s.enrollments)) == 0
        )
        for role in ("app_user", "google_auth_lookup"):
            scope(session, name, "a", role)
            with pytest.raises(sa.exc.DBAPIError), session.begin_nested():
                session.execute(sa.select(s.enrollments))
    with engine.begin() as conn:
        conn.exec_driver_sql(f"SET LOCAL search_path TO {name}")
        conn.exec_driver_sql("SET LOCAL ROLE migration_owner")
        with (
            pytest.raises(RuntimeError),
            conn.begin_nested(),
            Operations.context(MigrationContext.configure(conn)),
        ):
            migration28().downgrade()
        assert conn.exec_driver_sql(
            "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='webauthn_enrollments'::regclass"
        ).one() == (True, True)
        conn.exec_driver_sql("SELECT set_config('app.current_user_id','a',true)")
        assert conn.scalar(sa.select(s.enrollments.c.id)) == grant


def test_concurrent_registration_and_recovery_consumption(pg, redis_client):
    engine, name = pg
    sessions = auth.SessionStore()
    binding = p.Binding("a", sessions.create("a"), 1, "passkey_add")
    config = p.Config("app.example.com", "Vervfy", ("https://app.example.com",))
    gate = e.SecurityGate(redis_client, sessions)
    service = e.RegistrationService(
        config, p.ChallengeStore(redis_client), gate, clock=lambda: 1000
    )
    with Session(engine, info={"tenant_id": "a"}) as session, session.begin():
        scope(session, name)
        grant = e._grant(session, binding, "password", 1000)
        cid1, opts1 = service.begin(session, binding, grant)
        cid2, opts2 = service.begin(session, binding, grant)
    _, response1 = registration(opts1["challenge"], credential=b"first")
    _, response2 = registration(opts2["challenge"], credential=b"second")

    def finish(pair):
        try:
            with Session(engine, info={"tenant_id": "a"}) as session, session.begin():
                scope(session, name)
                return service.finish(session, binding, grant, *pair)
        except p.PasskeyError:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(finish, [(cid1, response1), (cid2, response2)]))
    assert sum(x is not None for x in results) == 1
    # No recovery endpoint exists; seed a hash to test the restricted consumer race.
    recovery = e.RecoveryCodes(config, gate, clock=lambda: 1000)
    binding = p.Binding("a", binding.session_id, 1, "recovery_rotate")
    code = secrets.token_hex(32)
    with Session(engine, info={"tenant_id": "a"}) as session, session.begin():
        scope(session, name)
        session.execute(
            s.recovery_codes.insert().values(
                id="code",
                user_id="a",
                code_hash=recovery.digest("a", code),
                created_at=1000,
            )
        )

    def consume(_):
        try:
            with Session(engine, info={"tenant_id": "a"}) as session, session.begin():
                scope(session, name)
                return recovery.consume(session, binding, code)
        except p.PasskeyError:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(consume, range(4)))
    assert sum(x is not None for x in results) == 1
    with Session(engine, info={"tenant_id": "a"}) as session, session.begin():
        scope(session, name)
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(s.recovery_states))
            == 1
        )
        assert session.scalar(sa.select(s.recovery_states.c.status)) == "pending"


def test_signup_creation_under_runtime_role_and_original_expiry(pg, redis_client):
    engine, name = pg
    sessions = auth.SessionStore()
    config = p.Config("app.example.com", "Vervfy", ("https://app.example.com",))
    service = e.RegistrationService(
        config,
        p.ChallengeStore(redis_client),
        e.SecurityGate(redis_client, sessions),
        clock=lambda: 1050,
    )
    oauth = object.__new__(GoogleOAuthService)
    oauth.transactions = RedisOAuthTransactionStore("", client=redis_client)
    oauth._clock = lambda: 1000
    oauth.lookup_identity = Mock(return_value=None)
    browser = secrets.token_urlsafe(32)
    oauth.store_pending_signup(browser, {"sub": browser, "email_verified": False})
    with Session(engine) as session, session.begin():
        scope(session, name, user="")
        binding, grant = service.create_google_signup(
            session, oauth, browser, "newpguser"
        )
    with (
        Session(engine, info={"tenant_id": binding.user_id}) as session,
        session.begin(),
    ):
        scope(session, name, binding.user_id)
        row = session.execute(sa.select(s.enrollments)).mappings().one()
        assert row["expires_at"] == 1300
        cid, opts = service.begin(session, binding, grant)
    _, response = registration(opts["challenge"], credential=browser.encode())
    with (
        Session(engine, info={"tenant_id": binding.user_id}) as session,
        session.begin(),
    ):
        scope(session, name, binding.user_id)
        service.finish(session, binding, grant, cid, response)
