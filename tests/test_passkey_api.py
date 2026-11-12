"""Passkey API integration checks using only an isolated SQLite database."""

import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

import passkey_schema
import server
from db import Base, User


@pytest.fixture
def passkey_db(monkeypatch):
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    passkey_schema.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    user_id = "passkey-api-user"
    session_id = "validated-session"
    intent_id = "i" * 43
    proof_id = "p" * 43
    now = int(time.time())
    with sessions.begin() as session:
        session.add_all(
            [
                User(
                    id=user_id,
                    username="passkey-user",
                    username_key="passkey-user",
                    email="old@example.com",
                    email_verified=True,
                    password_hash=None,
                    session_version=1,
                    created_at=now,
                ),
                User(
                    id="existing-email-user",
                    username="existing-email",
                    username_key="existing-email",
                    email="taken@example.com",
                    password_hash=None,
                    session_version=1,
                    created_at=now,
                ),
            ]
        )
        session.execute(
            passkey_schema.handles.insert().values(
                user_id=user_id, handle=b"h" * 32
            )
        )
        session.execute(
            passkey_schema.credentials.insert().values(
                id="credential-row",
                user_id=user_id,
                credential_id=b"credential-id",
                public_key=b"synthetic-key",
                algorithm=-7,
                sign_count=0,
                backup_eligible=False,
                backed_up=False,
                created_at=now,
            )
        )
        binding = server.passkeys.Binding(user_id, session_id, 1, "email_change")
        digest = server._passkey_action_digest(
            user_id, "email_change", "new@example.com"
        )
        session.execute(
            passkey_schema.intents.insert().values(
                id=intent_id,
                **binding.record(),
                payload_digest=digest,
                created_at=now - 1,
                expires_at=now + 299,
                consumed_at=None,
            )
        )
        session.execute(
            passkey_schema.proofs.insert().values(
                id=proof_id,
                user_id=user_id,
                intent_id=intent_id,
                credential_id="credential-row",
                verified_at=now - 1,
                expires_at=now + 299,
                consumed_at=None,
            )
        )

    monkeypatch.setattr(
        server,
        "tenant_session",
        lambda tenant: Session(
            engine, info={"tenant_id": tenant}, expire_on_commit=False
        ),
    )
    yield engine, sessions, user_id, session_id, intent_id, proof_id, now
    engine.dispose()


def _update_email(passkey_db, email):
    _engine, sessions, user_id, session_id, intent_id, proof_id, _now = passkey_db
    with sessions.begin() as session:
        session.execute(
            passkey_schema.intents.update()
            .where(passkey_schema.intents.c.id == intent_id)
            .values(
                payload_digest=server._passkey_action_digest(
                    user_id, "email_change", email.strip().lower()
                )
            )
        )
    with sessions() as session:
        user = session.get(User, user_id)
    request = SimpleNamespace(
        session={"user_id": user_id, "sid": session_id, "sv": 1}
    )
    with (
        patch.object(
            server,
            "_passkey_services",
            return_value=(object(), object(), object(), object()),
        ),
        patch.object(server, "_check_passkey_rate"),
        patch.object(server, "rotate_authenticated_session"),
    ):
        return server.change_account_email(
            server.EmailChangeRequest(
                email=email,
                passkey_intent_id=intent_id,
                passkey_proof_id=proof_id,
            ),
            request,
            user,
            _csrf=None,
        )


def test_passkey_email_proof_and_mutation_commit_together(passkey_db, monkeypatch):
    monkeypatch.setattr(server, "passkey_config", None)
    result = _update_email(passkey_db, "new@example.com")
    assert result == {"email": "new@example.com"}

    engine, _sessions, user_id, _sid, intent_id, proof_id, _now = passkey_db
    with engine.connect() as connection:
        assert connection.scalar(
            sa.select(User.email).where(User.id == user_id)
        ) == "new@example.com"
        assert connection.scalar(
            sa.select(User.session_version).where(User.id == user_id)
        ) == 2
        assert connection.scalar(
            sa.select(passkey_schema.intents.c.consumed_at).where(
                passkey_schema.intents.c.id == intent_id
            )
        ) is not None
        assert connection.scalar(
            sa.select(passkey_schema.proofs.c.consumed_at).where(
                passkey_schema.proofs.c.id == proof_id
            )
        ) is not None


def test_failed_email_mutation_rolls_back_passkey_proof(passkey_db):
    with pytest.raises(HTTPException) as caught:
        _update_email(passkey_db, "taken@example.com")
    assert caught.value.status_code == 409

    engine, _sessions, user_id, _sid, intent_id, proof_id, _now = passkey_db
    with engine.connect() as connection:
        assert connection.scalar(
            sa.select(User.email).where(User.id == user_id)
        ) == "old@example.com"
        assert connection.scalar(
            sa.select(passkey_schema.intents.c.consumed_at).where(
                passkey_schema.intents.c.id == intent_id
            )
        ) is None
        assert connection.scalar(
            sa.select(passkey_schema.proofs.c.consumed_at).where(
                passkey_schema.proofs.c.id == proof_id
            )
        ) is None


def test_passkey_api_is_not_exposed_when_feature_flag_is_disabled(monkeypatch):
    monkeypatch.setattr(server, "passkey_config", None)
    with pytest.raises(HTTPException) as caught:
        server._passkey_services()
    assert caught.value.status_code == 404


def test_passkey_request_bodies_have_strict_limits():
    limits = server.RequestSizeLimitMiddleware(
        lambda *_args: None,
        audio_bytes=50 * 1024 * 1024,
        image_bytes=5 * 1024 * 1024,
        overhead=1024 * 1024,
    )
    assert limits.limit_for("/api/account/passkeys/registration/complete") == 64 * 1024
    assert limits.limit_for("/api/account/passkeys/actions/email_change/options") == 16 * 1024
    assert limits.limit_for("/api/account/email") == 16 * 1024

