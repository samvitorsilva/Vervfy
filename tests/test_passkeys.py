"""Synthetic signatures and private disposable Redis; never application URLs."""

import concurrent.futures
import hashlib
import importlib.util
import json
import shutil
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import cbor2
import pytest
import redis
import sqlalchemy as sa
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.orm import Session
from webauthn.helpers import bytes_to_base64url as b64

import passkey_schema as s
import passkeys as p


@pytest.fixture(scope="module")
def redis_client(tmp_path_factory):
    root = tmp_path_factory.mktemp("passkeys-redis")
    binary = shutil.which("valkey-server") or shutil.which("redis-server")
    if not binary:
        pytest.fail("Local Redis/Valkey binary required")
    process = subprocess.Popen(
        [
            binary,
            "--port",
            "0",
            "--unixsocket",
            str(root / "redis.sock"),
            "--unixsocketperm",
            "700",
            "--save",
            "",
            "--appendonly",
            "no",
            "--dir",
            str(root),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    client = redis.Redis(unix_socket_path=str(root / "redis.sock"), socket_timeout=1)
    try:
        for _ in range(100):
            try:
                if client.ping():
                    break
            except redis.RedisError:
                time.sleep(0.02)
        else:
            pytest.fail("Private Redis did not start")
        yield client
    finally:
        client.close()
        process.terminate()
        process.wait(timeout=5)


def migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/0027_webauthn_foundation.py"
    )
    spec = importlib.util.spec_from_file_location("passkey_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def setup(redis_client):
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        s.metadata.create_all(conn)
        conn.execute(
            s.users.insert(),
            [{"id": "a", "session_version": 1}, {"id": "b", "session_version": 1}],
        )
        conn.execute(
            s.handles.insert(),
            [
                {"user_id": "a", "handle": b"a" * 32},
                {"user_id": "b", "handle": b"b" * 32},
            ],
        )
    key = ec.generate_private_key(ec.SECP256R1())
    numbers = key.public_key().public_numbers()
    public = cbor2.dumps(
        {
            1: 2,
            3: -7,
            -1: 1,
            -2: numbers.x.to_bytes(32, "big"),
            -3: numbers.y.to_bytes(32, "big"),
        }
    )
    with engine.begin() as conn:
        conn.execute(
            s.credentials.insert(),
            {
                "id": "credential",
                "user_id": "a",
                "credential_id": b"credential",
                "public_key": public,
                "algorithm": -7,
                "sign_count": 0,
                "backup_eligible": False,
                "backed_up": False,
                "created_at": 1000,
            },
        )
    service = p.AssertionService(
        p.Config("app.example.com", "Vervfy", ("https://app.example.com",)),
        p.ChallengeStore(redis_client),
        clock=lambda: 1000,
    )
    binding = p.Binding("a", "session", 1, "password_add")
    with Session(engine, info={"tenant_id": "a"}) as session, session.begin():
        intent = p.create_intent(session, binding, "a" * 64, now=1000)
    yield engine, key, service, binding, intent
    engine.dispose()


def assertion(
    key,
    challenge,
    *,
    origin="https://app.example.com",
    rp="app.example.com",
    flags=5,
    counter=1,
    credential=b"credential",
    handle=b"a" * 32,
    cross=False,
):
    client = json.dumps(
        {
            "type": "webauthn.get",
            "challenge": challenge,
            "origin": origin,
            "crossOrigin": cross,
        }
    ).encode()
    auth = (
        hashlib.sha256(rp.encode()).digest()
        + bytes([flags])
        + counter.to_bytes(4, "big")
    )
    signature = key.sign(
        auth + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256())
    )
    return {
        "id": b64(credential),
        "rawId": b64(credential),
        "type": "public-key",
        "response": {
            "clientDataJSON": b64(client),
            "authenticatorData": b64(auth),
            "signature": b64(signature),
            "userHandle": b64(handle),
        },
    }


def begin(data):
    engine, _key, service, binding, intent = data
    with (
        Session(engine, info={"tenant_id": binding.user_id}) as session,
        session.begin(),
    ):
        challenge_id, options = service.begin(session, binding, intent)
    return challenge_id, options


def finish(data, challenge_id, response, binding=None):
    engine, _key, service, original, intent = data
    binding = binding or original
    with (
        Session(engine, info={"tenant_id": binding.user_id}) as session,
        session.begin(),
    ):
        return service.finish(session, binding, intent, challenge_id, response)


def test_disabled_and_invalid_config(monkeypatch):
    monkeypatch.delenv("VERVFY_WEBAUTHN_ENABLED", raising=False)
    assert p.Config.from_environment() is None
    with pytest.raises(p.PasskeyUnavailable):
        p.AssertionService(None, p.ChallengeStore(Mock()))
    monkeypatch.setenv("VERVFY_WEBAUTHN_ENABLED", "1")
    monkeypatch.delenv("VERVFY_WEBAUTHN_RP_ID", raising=False)
    with pytest.raises(p.PasskeyError):
        p.Config.from_environment()


@pytest.mark.parametrize(
    "rp,origin",
    [
        ("test.trycloudflare.com", "https://test.trycloudflare.com"),
        ("app.example.com", "https://evil.example.com"),
        ("app.example.com", "http://app.example.com"),
        ("app.example.com", "https://app.example.com/path"),
        ("app.example.com", "https://app.example.com:444"),
        ("*.example.com", "https://app.example.com"),
        ("com", "https://com"),
    ],
)
def test_config_rejects_untrusted_values(rp, origin):
    with pytest.raises(p.PasskeyError):
        p.Config(rp, "Vervfy", (origin,))


def test_real_signature_proof_and_mutation_rollback(setup):
    cid, opts = begin(setup)
    assert opts["userVerification"] == "required"
    proof = finish(setup, cid, assertion(setup[1], opts["challenge"]))
    engine, _, _, binding, intent = setup
    with (
        pytest.raises(RuntimeError),
        Session(engine, info={"tenant_id": "a"}) as session,
        session.begin(),
    ):
        p.consume_proof(session, binding, intent, proof, "a" * 64, now=1000)
        session.execute(
            s.users.update().where(s.users.c.id == "a").values(session_version=2)
        )
        raise RuntimeError("mutation failed")
    with Session(engine, info={"tenant_id": "a"}) as session, session.begin():
        p.consume_proof(session, binding, intent, proof, "a" * 64, now=1000)
        session.execute(
            s.users.update().where(s.users.c.id == "a").values(session_version=2)
        )
    with (
        Session(engine, info={"tenant_id": "a"}) as session,
        session.begin(),
        pytest.raises(p.PasskeyError),
    ):
        p.consume_proof(session, binding, intent, proof, "a" * 64, now=1000)


@pytest.mark.parametrize(
    "changes",
    [
        {"origin": "https://evil.example.com"},
        {"rp": "evil.example.com"},
        {"flags": 1},
        {"flags": 4},
        {"cross": True},
        {"handle": b"b" * 32},
        {"credential": b"other"},
    ],
)
def test_invalid_assertion_never_issues_proof(setup, changes):
    cid, opts = begin(setup)
    with pytest.raises(p.PasskeyError):
        finish(setup, cid, assertion(setup[1], opts["challenge"], **changes))
    with setup[0].connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(s.proofs)) == 0
    with pytest.raises(p.PasskeyError):
        finish(setup, cid, assertion(setup[1], opts["challenge"]))


def test_bad_signature(setup):
    cid, opts = begin(setup)
    with pytest.raises(p.PasskeyError):
        finish(
            setup,
            cid,
            assertion(ec.generate_private_key(ec.SECP256R1()), opts["challenge"]),
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"user_id": "b"},
        {"session_id": "other"},
        {"action": "email_change"},
        {"session_version": 2},
    ],
)
def test_binding_mismatch(setup, changes):
    cid, opts = begin(setup)
    with pytest.raises(p.PasskeyError):
        finish(
            setup,
            cid,
            assertion(setup[1], opts["challenge"]),
            replace(setup[3], **changes),
        )


def test_expired_challenge(setup):
    cid, opts = begin(setup)
    setup[2].clock = lambda: 1120
    with pytest.raises(p.PasskeyError):
        finish(setup, cid, assertion(setup[1], opts["challenge"]))


def test_revocation_at_finish_and_consumption(setup):
    cid, opts = begin(setup)
    with setup[0].begin() as conn:
        conn.execute(s.credentials.update().values(revoked_at=1000))
    with pytest.raises(p.PasskeyError):
        finish(setup, cid, assertion(setup[1], opts["challenge"]))
    with setup[0].begin() as conn:
        conn.execute(s.credentials.update().values(revoked_at=None))
    cid, opts = begin(setup)
    proof = finish(setup, cid, assertion(setup[1], opts["challenge"]))
    with setup[0].begin() as conn:
        conn.execute(s.credentials.update().values(revoked_at=1000))
    with (
        Session(setup[0], info={"tenant_id": "a"}) as session,
        session.begin(),
        pytest.raises(p.PasskeyError),
    ):
        p.consume_proof(session, setup[3], setup[4], proof, "a" * 64, now=1000)


@pytest.mark.parametrize(
    "synced,counter,allowed",
    [(True, 0, True), (True, 3, True), (False, 3, False), (False, 11, True)],
)
def test_counter_policy(setup, synced, counter, allowed):
    with setup[0].begin() as conn:
        conn.execute(
            s.credentials.update().values(sign_count=10, backup_eligible=synced)
        )
    cid, opts = begin(setup)
    response = assertion(
        setup[1], opts["challenge"], flags=13 if synced else 5, counter=counter
    )
    if allowed:
        finish(setup, cid, response)
    else:
        with pytest.raises(p.PasskeyError):
            finish(setup, cid, response)


def test_atomic_challenge_and_redis_expiry(redis_client):
    store = p.ChallengeStore(redis_client)
    identifier = store.create({"test": True})

    def consume(_):
        try:
            return store.consume(identifier)
        except p.PasskeyError:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(x is not None for x in executor.map(consume, range(8))) == 1
    identifier = store.create({"test": True})
    assert 0 < redis_client.ttl(store.PREFIX + identifier) <= p.CHALLENGE_TTL
    redis_client.pexpire(store.PREFIX + identifier, 1)
    time.sleep(0.02)
    with pytest.raises(p.PasskeyError):
        store.consume(identifier)


def test_backend_outage_fails_closed():
    client = Mock()
    client.set.side_effect = redis.ConnectionError()
    client.eval.side_effect = redis.ConnectionError()
    store = p.ChallengeStore(client)
    with pytest.raises(p.PasskeyUnavailable):
        store.create({})
    with pytest.raises(p.PasskeyUnavailable):
        store.consume("a" * 43)


def test_database_outage_burns_challenge_without_proof(setup):
    cid, opts = begin(setup)
    session = Mock(info={"tenant_id": "a"})
    session.execute.side_effect = sa.exc.OperationalError("local test", {}, Exception())
    with pytest.raises(sa.exc.OperationalError):
        setup[2].finish(
            session, setup[3], setup[4], cid, assertion(setup[1], opts["challenge"])
        )
    with pytest.raises(p.PasskeyError):
        finish(setup, cid, assertion(setup[1], opts["challenge"]))


def test_sqlite_migration_guards_existing_security_data():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    engine = sa.create_engine("sqlite://")
    m = migration()
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE users(id VARCHAR(32) PRIMARY KEY, session_version INTEGER)"
        )
        conn.exec_driver_sql("INSERT INTO users VALUES ('a',7)")
        with Operations.context(MigrationContext.configure(conn)):
            m.upgrade()
            m.downgrade()
            m.upgrade()
            conn.execute(m.handles.insert().values(user_id="a", handle=b"a" * 32))
            with pytest.raises(RuntimeError):
                m.downgrade()
        assert conn.exec_driver_sql("SELECT session_version FROM users").scalar() == 7
    engine.dispose()


def test_valid_configuration_and_no_header_trust(monkeypatch):
    monkeypatch.setenv("VERVFY_WEBAUTHN_ENABLED", "1")
    monkeypatch.setenv("VERVFY_WEBAUTHN_RP_ID", "app.example.com")
    monkeypatch.setenv("VERVFY_WEBAUTHN_RP_NAME", "Vervfy")
    monkeypatch.setenv("VERVFY_WEBAUTHN_ORIGINS", '["https://app.example.com"]')
    assert p.Config.from_environment().origins == ("https://app.example.com",)
    monkeypatch.setenv("VERVFY_WEBAUTHN_ORIGINS", "[]")
    with pytest.raises(p.PasskeyError):
        p.Config.from_environment()


@pytest.mark.parametrize(
    "case", ["payload", "intent", "session", "action", "expired", "replay"]
)
def test_proof_binding_and_expiry(setup, case):
    cid, opts = begin(setup)
    proof = finish(setup, cid, assertion(setup[1], opts["challenge"]))
    engine, _, _, binding, intent = setup
    if case == "replay":
        with Session(engine, info={"tenant_id": "a"}) as session, session.begin():
            p.consume_proof(session, binding, intent, proof, "a" * 64, now=1000)
    if case == "session":
        binding = replace(binding, session_id="other")
    if case == "action":
        binding = replace(binding, action="email_change")
    with (
        Session(engine, info={"tenant_id": "a"}) as session,
        session.begin(),
        pytest.raises(p.PasskeyError),
    ):
        p.consume_proof(
            session,
            binding,
            "wrong" if case == "intent" else intent,
            proof,
            "b" * 64 if case == "payload" else "a" * 64,
            now=1300 if case == "expired" else 1000,
        )


def test_backup_eligibility_is_immutable(setup):
    cid, opts = begin(setup)
    with pytest.raises(p.PasskeyError):
        finish(setup, cid, assertion(setup[1], opts["challenge"], flags=13))


def test_wrong_challenge_and_malformed_input(setup):
    cid, _opts = begin(setup)
    with pytest.raises(p.PasskeyError):
        finish(setup, cid, assertion(setup[1], b64(b"wrong")))
    cid, _opts = begin(setup)
    with pytest.raises(p.PasskeyError):
        finish(setup, cid, {"id": "bad"})


def test_no_credentials_or_tenant_transaction(setup):
    engine, _, service, binding, intent = setup
    with (
        Session(engine, info={"tenant_id": "b"}) as session,
        session.begin(),
        pytest.raises(p.PasskeyError),
    ):
        service.begin(session, binding, intent)
    with engine.begin() as conn:
        conn.execute(s.credentials.update().values(revoked_at=1000))
    with pytest.raises(p.PasskeyError):
        begin(setup)


def test_migration_graph_is_additive():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    graph = ScriptDirectory.from_config(Config("alembic.ini"))
    assert graph.get_heads() == ["0028_webauthn_enrollment"]
    assert (
        graph.get_revision("0027_webauthn_foundation").down_revision
        == "0026_application_runtime_grants"
    )
    migrated = migration()
    for current, frozen in zip(s.TABLES, migrated.TABLES, strict=True):
        assert current.name == frozen.name
        assert [(c.name, str(c.type), c.nullable) for c in current.columns] == [
            (c.name, str(c.type), c.nullable) for c in frozen.columns
        ]
