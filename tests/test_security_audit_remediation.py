"""Synthetic regressions; these do not claim PostgreSQL RLS/concurrency proof."""

import os
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

import auth
import db
import password_reset
import storage_lifecycle
from runtime_environment import runtime_environment


@pytest.fixture
def account(monkeypatch):
    engine = create_engine("sqlite://")
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(auth, "SessionLocal", factory)
    monkeypatch.setattr(auth, "tenant_session", lambda _: factory())
    with factory.begin() as s:
        s.add(
            db.User(
                id="audit",
                username="audit",
                username_key="audit",
                email="audit@example.invalid",
                email_verified=True,
                password_hash="synthetic-original-hash",
                session_version=3,
                created_at=1,
            )
        )
    # Tests exercise state comparisons, not bcrypt performance.
    monkeypatch.setattr(auth, "hash_password", lambda _: "synthetic-reset-hash")
    yield auth.UserStore(), factory
    engine.dispose()


@pytest.mark.parametrize(
    "mutation", ["password", "version", "email", "unverified", "deleted"]
)
def test_unused_reset_link_rejected_after_security_state_change(account, mutation):
    users, factory = account
    tokens = password_reset.PasswordResetStore()
    token = tokens.issue("audit", binding=users.get_password_reset_binding("audit"))
    with factory.begin() as s:
        row = s.get(db.User, "audit")
        if mutation == "password":
            row.password_hash = "new-credential"
        elif mutation == "version":
            row.session_version += 1
        elif mutation == "email":
            row.email = "changed@example.invalid"
        elif mutation == "unverified":
            row.email_verified = False
        else:
            s.delete(row)
    claim = tokens.claim(token)
    assert claim is not None
    with pytest.raises(ValueError):
        users.reset_password_and_invalidate_sessions(
            "audit", "new-password-123", expected_binding=claim.binding
        )
    with factory() as s:
        row = s.get(db.User, "audit")
        assert row is None or row.password_hash != "synthetic-reset-hash"


def test_change_password_invalidates_already_claimed_reset(account):
    users, factory = account
    tokens = password_reset.PasswordResetStore()
    token = tokens.issue("audit", binding=users.get_password_reset_binding("audit"))
    claim = tokens.claim(token)
    users.set_password_and_bump_version(
        "audit", "changed-hash", expected_password_hash="synthetic-original-hash"
    )
    with pytest.raises(ValueError, match="invalid or has expired"):
        users.reset_password_and_invalidate_sessions(
            "audit", "new-password-123", expected_binding=claim.binding
        )
    with factory() as s:
        assert s.get(db.User, "audit").password_hash == "changed-hash"


def test_current_reset_binding_succeeds_once_and_cannot_cross_accounts(account):
    users, factory = account
    binding = users.get_password_reset_binding(
        "audit", expected_email="audit@example.invalid"
    )
    assert binding is not None
    assert (
        users.get_password_reset_binding(
            "audit", expected_email="other@example.invalid"
        )
        is None
    )
    assert (
        users.get_password_reset_binding("audit", expected_email_digest="wrong") is None
    )
    with factory.begin() as s:
        s.add(
            db.User(
                id="other",
                username="other",
                username_key="other",
                email="other@example.invalid",
                email_verified=True,
                password_hash="synthetic-original-hash",
                session_version=3,
                created_at=1,
            )
        )
    with pytest.raises(ValueError):
        users.reset_password_and_invalidate_sessions(
            "other", "new-password-123", expected_binding=binding
        )
    assert (
        users.reset_password_and_invalidate_sessions(
            "audit", "new-password-123", expected_binding=binding
        )
        == 4
    )
    with pytest.raises(ValueError):
        users.reset_password_and_invalidate_sessions(
            "audit", "new-password-123", expected_binding=binding
        )
    with factory() as s:
        assert (
            s.scalar(select(db.User.password_hash).where(db.User.id == "other"))
            == "synthetic-original-hash"
        )


@pytest.mark.parametrize("binding", [None, "", "legacy-or-invalid-binding"])
def test_unbound_reset_links_fail_closed(account, binding):
    users, _ = account
    with pytest.raises(ValueError):
        users.reset_password_and_invalidate_sessions(
            "audit", "new-password-123", expected_binding=binding
        )


@pytest.mark.parametrize(
    "env",
    [
        {"VERVFY_ENVIRONMENT": "production"},
        {"VERVFY_ENVIRONMENT": " PrOd "},
        {"ENVIRONMENT": "production"},
        {"ENVIRONMENT": "PROD"},
        {"VERVFY_ENVIRONMENT": " ", "ENVIRONMENT": "prod"},
    ],
)
@pytest.mark.parametrize(
    "mode", ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]
)
def test_all_production_aliases_enforce_authenticated_tls(env, mode):
    with patch.dict(
        os.environ,
        {
            **env,
            "DATABASE_URL": f"postgresql://synthetic@db.example.invalid/audit?sslmode={mode}&gssencmode=prefer",
        },
        clear=True,
    ):
        assert runtime_environment() == "production"
        url = make_url(db.database_url())
        assert url.query["sslmode"] == "verify-full"
        assert url.query["gssencmode"] == "disable"
        assert url.query["sslrootcert"] == "system"


def test_explicit_ca_is_preserved_and_development_is_not_rewritten():
    original = (
        "postgresql://synthetic@db.example.invalid/audit?sslrootcert=/synthetic/ca.pem"
    )
    with patch.dict(
        os.environ, {"VERVFY_ENVIRONMENT": "prod", "DATABASE_URL": original}, clear=True
    ):
        assert make_url(db.database_url()).query["sslrootcert"] == "/synthetic/ca.pem"
    with patch.dict(
        os.environ,
        {"VERVFY_ENVIRONMENT": "development", "DATABASE_URL": original},
        clear=True,
    ):
        assert db.database_url() == db.normalize_database_url(original)


def test_upload_accounts_exact_size_before_io_and_holds_ambiguous_failure(
    tmp_path, monkeypatch
):
    source = tmp_path / "synthetic.mp3"
    source.write_bytes(b"synthetic")
    events = []
    reservation = storage_lifecycle.Reservation("id", "path", "token")
    monkeypatch.setattr(storage_lifecycle, "local_storage_selected", lambda: False)

    def reserve(user, kind, ext, size):
        assert (user, kind, ext, size) == ("audit", "staged-audio", "mp3", 9)
        events.append("charged")
        return reservation

    monkeypatch.setattr(storage_lifecycle, "_reserve", reserve)
    monkeypatch.setattr(
        storage_lifecycle, "_advance", lambda u, r, state: events.append(state)
    )
    monkeypatch.setattr(storage_lifecycle, "_binding", lambda *args: object())

    def transfer(factory):
        assert events == ["charged", "uploading"]
        raise TimeoutError("synthetic timeout")

    monkeypatch.setattr(storage_lifecycle, "_run", transfer)
    with pytest.raises(TimeoutError):
        storage_lifecycle.upload_file(
            "audit", "staged-audio", str(source), "audio/mpeg", "mp3"
        )
    assert events == ["charged", "uploading", "hold"]


def test_reservation_failure_prevents_storage_io(tmp_path, monkeypatch):
    source = tmp_path / "synthetic.mp3"
    source.write_bytes(b"synthetic")
    monkeypatch.setattr(storage_lifecycle, "local_storage_selected", lambda: False)
    reserve = Mock(side_effect=RuntimeError("synthetic transaction failure"))
    io = Mock()
    monkeypatch.setattr(storage_lifecycle, "_reserve", reserve)
    monkeypatch.setattr(storage_lifecycle, "_run", io)
    with pytest.raises(RuntimeError):
        storage_lifecycle.upload_file(
            "audit", "audio", str(source), "audio/mpeg", "mp3"
        )
    io.assert_not_called()


def test_reported_quota_includes_retired_allocations(account, monkeypatch):
    import library

    _, factory = account
    monkeypatch.setattr(library, "tenant_session", lambda _: factory())
    monkeypatch.setattr(library.audio_store, "enabled", lambda: True)
    monkeypatch.setattr(storage_lifecycle, "retained_bytes", lambda user: 1024)
    with factory.begin() as s:
        s.add(
            db.TrackRecord(
                id="synthetic",
                user_id="audit",
                filename="x",
                title="x",
                artist="x",
                album="x",
                size_bytes=1024,
            )
        )
    lib = library.Library("audit")
    assert lib.total_bytes() == 1024
    assert lib.remove("synthetic")
    assert lib.total_bytes() == 1024


def test_real_reset_route_passes_binding_and_rejects_stale_link(account, monkeypatch):
    from fastapi import HTTPException
    from starlette.requests import Request

    import server

    users, _ = account
    tokens = password_reset.PasswordResetStore()
    mailer = Mock()
    monkeypatch.setenv("VERVFY_PASSWORD_RECOVERY_ENABLED", "1")
    monkeypatch.setattr(server, "user_store", users)
    monkeypatch.setattr(server, "password_reset_store", tokens)
    monkeypatch.setattr(server, "email_sender", mailer)
    monkeypatch.setattr(server.request_throttle, "allow", lambda *a, **k: True)
    revoke = Mock()
    monkeypatch.setattr(server.session_store, "revoke_user", revoke)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/forgot-password",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "session": {},
        }
    )
    server.forgot_password(
        server.ForgotPasswordRequest(email="audit@example.invalid"), request, _csrf=None
    )
    token = mailer.send_password_reset.call_args.kwargs["token"]
    users.set_password_and_bump_version(
        "audit", "changed-hash", expected_password_hash="synthetic-original-hash"
    )
    with pytest.raises(HTTPException) as error:
        server.reset_password(
            server.ResetPasswordRequest(token=token, password="new-password-123"),
            request,
            _csrf=None,
        )
    assert error.value.status_code == 400
    revoke.assert_not_called()


def test_email_verification_link_cannot_restore_stale_reset_authority(account):
    users, factory = account
    with factory.begin() as s:
        s.get(db.User, "audit").email_verified = False
    old_binding = users.get_password_reset_binding("audit", verified=False)
    users.set_password_and_bump_version(
        "audit", "changed-hash", expected_password_hash="synthetic-original-hash"
    )
    with pytest.raises(ValueError):
        users.verify_password_reset_email("audit", old_binding)
    fresh = users.get_password_reset_binding("audit", verified=False)
    post_verification = users.verify_password_reset_email("audit", fresh)
    assert post_verification == users.get_password_reset_binding("audit")
    users.bump_session_version("audit")
    with pytest.raises(ValueError):
        users.reset_password_and_invalidate_sessions(
            "audit", "new-password-123", expected_binding=post_verification
        )


@pytest.mark.parametrize("failure", ["quota", "database", "commit"])
def test_actual_reservation_failure_never_reaches_provider(
    tmp_path, monkeypatch, failure
):
    from unittest.mock import MagicMock

    from sqlalchemy.exc import OperationalError

    import audio_store

    source = tmp_path / "synthetic.mp3"
    source.write_bytes(b"synthetic")
    session = MagicMock()
    session.bind.dialect.name = "postgresql"
    session.__enter__.return_value = session
    monkeypatch.setattr(storage_lifecycle, "tenant_session", lambda _: session)
    monkeypatch.setattr(storage_lifecycle, "local_storage_selected", lambda: False)
    monkeypatch.setattr(storage_lifecycle, "bound_transaction", lambda _: None)
    monkeypatch.setattr(storage_lifecycle, "_validate", lambda *a: None)
    monkeypatch.setattr(storage_lifecycle, "validate_local_session", lambda _: None)
    provider = Mock()
    monkeypatch.setattr(storage_lifecycle, "_run", provider)
    cause = Exception("synthetic provider credentials must not appear")
    cause.sqlstate = "54000" if failure == "quota" else "08006"
    error = OperationalError("synthetic statement", {}, cause)
    if failure == "commit":
        session.commit.side_effect = error
    else:
        session.execute.side_effect = error
    expected = (
        storage_lifecycle.RetainedStorageQuotaExceeded
        if failure == "quota"
        else audio_store.StorageError
    )
    with pytest.raises(expected) as caught:
        storage_lifecycle.upload_file(
            "audit", "audio", str(source), "audio/mpeg", "mp3"
        )
    provider.assert_not_called()
    assert "credentials" not in str(caught.value)
    assert caught.value.__suppress_context__
