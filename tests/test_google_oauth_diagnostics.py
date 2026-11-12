"""Local diagnostics and access-log privacy regression tests (no network)."""
import logging
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
    }), pytest.raises(google_oauth.GoogleTokenError):
        service.require_fresh_authentication({"sub": "private-subject", "iat": 1000})
    assert "freshness_missing_auth_time" in caplog.text
    assert "private-subject" not in caplog.text


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
