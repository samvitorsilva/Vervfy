"""Local diagnostics and access-log privacy regression tests (no network)."""
import asyncio
import logging
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import google_oauth


def test_callback_access_log_removes_all_parameters():
    record = logging.LogRecord(
        "uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %s',
        ("127.0.0.1", "GET", google_oauth.CALLBACK_PATH + "?code=secret&state=private", "1.1", 303), None,
    )
    assert google_oauth.OAuthAccessLogFilter().filter(record)
    assert "secret" not in record.getMessage()
    assert "private" not in record.getMessage()
    assert google_oauth.CALLBACK_PATH in record.getMessage()


@pytest.mark.parametrize("environment,enabled,expected", [
    ("development", "1", True), ("production", "1", False),
    ("", "1", False), ("development", "0", False),
])
def test_diagnostics_require_explicit_local_opt_in(caplog, environment, enabled, expected):
    with patch.dict("os.environ", {
        "VERVFY_ENVIRONMENT": environment,
        "VERVFY_GOOGLE_OAUTH_DIAGNOSTICS": enabled,
    }):
        google_oauth.local_diagnostic("proof_storage")
    assert bool(caplog.records) is expected


def test_missing_auth_time_fails_closed_with_safe_diagnostic(caplog):
    service = object.__new__(google_oauth.GoogleOAuthService)
    service._clock = lambda: 1000
    with patch.dict("os.environ", {
        "VERVFY_ENVIRONMENT": "development",
        "VERVFY_GOOGLE_OAUTH_DIAGNOSTICS": "1",
    }), pytest.raises(google_oauth.GoogleFreshnessError) as error:
        service.require_fresh_authentication({"sub": "private-subject", "iat": 1000})
    assert "freshness_missing_auth_time" in caplog.text
    assert "private-subject" not in caplog.text
    assert error.value.failure_stage == "freshness_missing_auth_time"


@pytest.mark.parametrize(
    "failure,expected_stage",
    [
        ("missing_auth_time", "freshness_missing_auth_time"),
        ("stale_auth_time", "freshness_stale_auth_time"),
        ("session_binding", "account_session_binding"),
        ("transaction", "transaction"),
        ("token_validation", "other_validation"),
        ("login_validation", None),
    ],
)
def test_production_reauth_failure_logs_only_fixed_stage(
    caplog, failure, expected_stage
):
    import server

    now = int(time.time())

    class ReauthService:
        _clock = staticmethod(lambda: now)

        async def consume_transaction(self, state, browser_binding):
            if failure == "transaction":
                raise google_oauth.OAuthTransactionError(state)
            return {
                "purpose": "login" if failure == "login_validation" else "password_add",
                "user_id": "private-user",
                "session_id": "session-1",
                "session_version": 3,
            }

        async def exchange_and_validate(self, code, transaction):
            if failure in {"token_validation", "login_validation"}:
                raise google_oauth.GoogleTokenError(code)
            claims = {
                "email": "private@example.com",
                "email_verified": True,
                "sub": "private-subject",
            }
            if failure == "stale_auth_time":
                claims["auth_time"] = now - 301
            elif failure != "missing_auth_time":
                claims["auth_time"] = now
            return claims

        def lookup_identity(self, claims):
            return "private-user"

        def require_fresh_authentication(self, claims):
            return google_oauth.GoogleOAuthService.require_fresh_authentication(
                self, claims
            )

    config = SimpleNamespace(
        browser_cookie_name="google_binding",
        cookie_secure=True,
        require_test_user=lambda email, *, email_verified: None,
    )
    request = SimpleNamespace(
        query_params={"state": "private-state", "code": "private-code"},
        cookies={config.browser_cookie_name: "private-cookie"},
        session={
            "user_id": "private-user",
            "sid": "other-session" if failure == "session_binding" else "session-1",
            "sv": 3,
        },
    )
    caplog.set_level(logging.WARNING, logger="vervfy.oauth")
    with (
        patch.dict("os.environ", {"VERVFY_ENVIRONMENT": "production"}),
        patch.object(server, "google_oauth_config", config),
        patch.object(server, "google_oauth_service", ReauthService()),
        patch.object(
            server,
            "current_user_row",
            return_value={"id": "private-user", "session_version": 3},
        ),
    ):
        response = asyncio.run(server.google_oauth_callback(request))

    assert response.status_code == 303
    records = [
        record
        for record in caplog.records
        if record.name == "vervfy.oauth"
    ]
    if expected_stage is None:
        assert records == []
    else:
        message = (
            "Google OAuth callback failure"
            if expected_stage == "transaction"
            else "Google reauthentication failure"
        )
        assert [record.getMessage() for record in records] == [
            f"{message} stage={expected_stage}"
        ]
    for private_value in (
        "private-state",
        "private-code",
        "private-cookie",
        "private@example.com",
        "private-user",
    ):
        assert private_value not in caplog.text


def test_production_failure_logger_reduces_unknown_stage_to_fixed_value(caplog):
    caplog.set_level(logging.WARNING, logger="vervfy.oauth")
    with patch.dict("os.environ", {"VERVFY_ENVIRONMENT": "production"}):
        google_oauth.log_google_reauthentication_failure("private-authorization-code")
    assert caplog.text.strip().endswith(
        "Google reauthentication failure stage=other_validation"
    )
    assert "private-authorization-code" not in caplog.text


def test_google_only_password_creation_consumes_bound_proof():
    import time
    from types import SimpleNamespace
    from unittest.mock import Mock
    import server

    user = {"id": "local-user", "password_hash": None, "session_version": 2}
    request = SimpleNamespace(session={"sid": "local-session", "sv": 2})
    proof = dict(purpose="password_add", user_id=user["id"],
                 session_id="local-session", session_version=2,
                 auth_time=int(time.time()), verified_at=int(time.time()))
    service = Mock()
    service.consume_reauthentication_proof.side_effect = [proof, None]
    with patch.object(server, "google_oauth_service", service), patch.object(
        server.user_store, "account_security", return_value={"google_linked": True}
    ), patch.object(server.user_store, "set_password_and_bump_version", return_value=3) as save, patch.object(
        server, "rotate_authenticated_session"
    ) as rotate:
        payload = server.PasswordChangeRequest(new_password="local-strong-password-123")
        assert server.change_password(payload, request, user) == {"ok": True}
        assert save.call_args.kwargs["expected_password_hash"] is None
        rotate.assert_called_once_with(request, "local-user", 3)
        with pytest.raises(server.HTTPException) as error:
            server.change_password(payload, request, user)
        assert error.value.status_code == 403
        assert save.call_count == 1
