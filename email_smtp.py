"""Transactional email via SMTP or Mailjet Send API v3.1.

Select the transport with EMAIL_TRANSPORT=smtp|mailjet_api (default: smtp).
SMTP uses VERVFY_SMTP_* variables. Mailjet uses VERVFY_MAILJET_API_KEY and
VERVFY_MAILJET_SECRET_KEY over HTTPS; it never falls back to SMTP.
"""

from __future__ import annotations

import errno
import json
import logging
import os
import smtplib
import socket
import ssl
from collections.abc import Callable
from email.message import EmailMessage
from email.utils import parseaddr
from html import escape
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger("vervfy.email")

# Safe, fixed reason codes for delivery diagnostics. Never derive these from
# exception messages, credentials, addresses, tokens, URLs, or provider bodies.
SMTP_REASON_CONNECTION_TIMEOUT = "connection_timeout"
SMTP_REASON_DNS_FAILURE = "dns_failure"
SMTP_REASON_AUTHENTICATION_FAILURE = "authentication_failure"
SMTP_REASON_TLS_FAILURE = "tls_failure"
SMTP_REASON_SMTP_RESPONSE_ERROR = "smtp_response_error"
SMTP_REASON_PROVIDER_ERROR = "provider_error"
SMTP_REASON_NOT_CONFIGURED = "not_configured"
SMTP_REASON_RATE_LIMITED = "rate_limited"
SMTP_REASON_MESSAGE_REJECTED = "message_rejected"
SMTP_REASON_MALFORMED_RESPONSE = "malformed_response"

_SMTP_REASON_CODES = frozenset(
    {
        SMTP_REASON_CONNECTION_TIMEOUT,
        SMTP_REASON_DNS_FAILURE,
        SMTP_REASON_AUTHENTICATION_FAILURE,
        SMTP_REASON_TLS_FAILURE,
        SMTP_REASON_SMTP_RESPONSE_ERROR,
        SMTP_REASON_PROVIDER_ERROR,
        SMTP_REASON_NOT_CONFIGURED,
        SMTP_REASON_RATE_LIMITED,
        SMTP_REASON_MESSAGE_REJECTED,
        SMTP_REASON_MALFORMED_RESPONSE,
    }
)

MAILJET_SEND_URL = "https://api.mailjet.com/v3.1/send"
_MAILJET_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
_EMAIL_TRANSPORT_SMTP = "smtp"
_EMAIL_TRANSPORT_MAILJET_API = "mailjet_api"


class EmailTransport(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class SmtpConfigError(RuntimeError):
    """Outbound email is not configured."""

    reason = SMTP_REASON_NOT_CONFIGURED


class SmtpSendError(RuntimeError):
    """Outbound email relay rejected or failed the message."""

    def __init__(
        self,
        message: str = "Could not send email",
        *,
        reason: str = SMTP_REASON_PROVIDER_ERROR,
    ):
        super().__init__(message)
        self.reason = reason if reason in _SMTP_REASON_CODES else SMTP_REASON_PROVIDER_ERROR


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _normalize_reason(reason: str) -> str:
    return reason if reason in _SMTP_REASON_CODES else SMTP_REASON_PROVIDER_ERROR


def _classify_one_smtp_exception(exc: BaseException) -> str | None:
    if isinstance(exc, SmtpSendError):
        # Prefer an already-specific reason; keep walking when only generic.
        if exc.reason != SMTP_REASON_PROVIDER_ERROR:
            return exc.reason
        return None
    if isinstance(exc, SmtpConfigError):
        return SMTP_REASON_NOT_CONFIGURED
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return SMTP_REASON_AUTHENTICATION_FAILURE
    if isinstance(exc, ssl.SSLError):
        return SMTP_REASON_TLS_FAILURE
    if isinstance(exc, socket.gaierror):
        return SMTP_REASON_DNS_FAILURE
    if isinstance(exc, (TimeoutError, socket.timeout, httpx.TimeoutException)):
        return SMTP_REASON_CONNECTION_TIMEOUT
    if isinstance(exc, OSError) and exc.errno in {
        errno.ETIMEDOUT,
        getattr(errno, "ETIME", errno.ETIMEDOUT),
    }:
        return SMTP_REASON_CONNECTION_TIMEOUT
    if isinstance(exc, smtplib.SMTPNotSupportedError):
        # STARTTLS unavailable or refused by the relay.
        return SMTP_REASON_TLS_FAILURE
    if isinstance(exc, smtplib.SMTPResponseException):
        return SMTP_REASON_SMTP_RESPONSE_ERROR
    if isinstance(exc, smtplib.SMTPException):
        return SMTP_REASON_SMTP_RESPONSE_ERROR
    if isinstance(exc, httpx.ConnectError):
        cause = exc.__cause__ or exc.__context__
        if isinstance(cause, socket.gaierror):
            return SMTP_REASON_DNS_FAILURE
        if isinstance(cause, ssl.SSLError):
            return SMTP_REASON_TLS_FAILURE
        return SMTP_REASON_PROVIDER_ERROR
    if isinstance(exc, httpx.HTTPError):
        return SMTP_REASON_PROVIDER_ERROR
    return None


def classify_smtp_failure(exc: BaseException) -> str:
    """Map a transport failure to a fixed reason code without reading messages."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        reason = _classify_one_smtp_exception(current)
        if reason is not None:
            return reason
        current = current.__cause__ or current.__context__
    return SMTP_REASON_PROVIDER_ERROR


def smtp_failure_reason(exc: BaseException) -> str:
    """Safe reason for logging; never returns exception text."""
    if isinstance(exc, SmtpConfigError):
        return SMTP_REASON_NOT_CONFIGURED
    if isinstance(exc, SmtpSendError) and exc.reason != SMTP_REASON_PROVIDER_ERROR:
        return exc.reason
    return classify_smtp_failure(exc)


def _reject_resend_test_sender(mail_from: str) -> None:
    sender = parseaddr(mail_from)[1].lower()
    if sender == "onboarding@resend.dev" and _env("VERVFY_ENVIRONMENT").lower() not in {
        "development",
        "local",
        "local-test",
        "staging",
        "test",
    }:
        raise SmtpConfigError(
            "onboarding@resend.dev is restricted to explicit non-production testing"
        )


class SmtpSettings:
    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        mail_from: str | None = None,
        use_starttls: bool | None = None,
    ):
        self.host = host if host is not None else _env("VERVFY_SMTP_HOST")
        raw_port = port if port is not None else _env("VERVFY_SMTP_PORT") or "587"
        try:
            self.port = int(raw_port)
        except (TypeError, ValueError) as exc:
            raise SmtpConfigError("VERVFY_SMTP_PORT must be an integer") from exc
        self.username = username if username is not None else _env("VERVFY_SMTP_USERNAME")
        self.password = password if password is not None else _env("VERVFY_SMTP_PASSWORD")
        self.mail_from = mail_from if mail_from is not None else _env("VERVFY_EMAIL_FROM")
        if use_starttls is None:
            # Port 465 conventionally wraps TLS; 587 uses STARTTLS.
            self.use_starttls = self.port != 465
        else:
            self.use_starttls = use_starttls

    def require_ready(self) -> None:
        if not self.host or not self.mail_from:
            raise SmtpConfigError("SMTP host and VERVFY_EMAIL_FROM are required")
        if _env("VERVFY_ENVIRONMENT").lower() == "production" and (
            self.port != 587 or not self.use_starttls
        ):
            raise SmtpConfigError("Production SMTP must use STARTTLS on port 587")
        if _env("VERVFY_ENVIRONMENT").lower() == "production" and (
            not self.username or not self.password
        ):
            raise SmtpConfigError("Production SMTP username and password are required")
        _reject_resend_test_sender(self.mail_from)


class SmtpTransport:
    def __init__(self, settings: SmtpSettings | None = None):
        self.settings = settings or SmtpSettings()

    def send(self, message: EmailMessage) -> None:
        self.settings.require_ready()
        settings = self.settings
        context = ssl.create_default_context()
        try:
            if settings.use_starttls:
                with smtplib.SMTP(settings.host, settings.port, timeout=20) as client:
                    client.ehlo()
                    client.starttls(context=context)
                    client.ehlo()
                    if settings.username:
                        client.login(settings.username, settings.password)
                    client.send_message(message)
            else:
                with smtplib.SMTP_SSL(
                    settings.host, settings.port, context=context, timeout=20
                ) as client:
                    if settings.username:
                        client.login(settings.username, settings.password)
                    client.send_message(message)
        except SmtpConfigError:
            raise
        except SmtpSendError:
            raise
        except Exception as exc:
            raise SmtpSendError(
                "Could not send email",
                reason=classify_smtp_failure(exc),
            ) from exc


class MailjetSettings:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        secret_key: str | None = None,
        mail_from: str | None = None,
        send_url: str | None = None,
    ):
        self.api_key = api_key if api_key is not None else _env("VERVFY_MAILJET_API_KEY")
        self.secret_key = (
            secret_key if secret_key is not None else _env("VERVFY_MAILJET_SECRET_KEY")
        )
        self.mail_from = mail_from if mail_from is not None else _env("VERVFY_EMAIL_FROM")
        self.send_url = send_url if send_url is not None else MAILJET_SEND_URL

    def require_ready(self) -> None:
        if not self.mail_from:
            raise SmtpConfigError("VERVFY_EMAIL_FROM is required")
        if not self.api_key or not self.secret_key:
            raise SmtpConfigError(
                "VERVFY_MAILJET_API_KEY and VERVFY_MAILJET_SECRET_KEY are required"
            )
        if (
            self.send_url != MAILJET_SEND_URL
            and _env("VERVFY_ENVIRONMENT").lower() == "production"
        ):
            raise SmtpConfigError("Production Mailjet must use the official Send API URL")
        _reject_resend_test_sender(self.mail_from)


def _message_text_and_html(message: EmailMessage) -> tuple[str | None, str | None]:
    text_part: str | None = None
    html_part: str | None = None
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_maintype() == "multipart":
                continue
            content_type = part.get_content_type()
            content = part.get_content()
            if not isinstance(content, str):
                continue
            if content_type == "text/plain" and text_part is None:
                text_part = content
            elif content_type == "text/html" and html_part is None:
                html_part = content
    else:
        content = message.get_content()
        if isinstance(content, str):
            if message.get_content_type() == "text/html":
                html_part = content
            else:
                text_part = content
    return text_part, html_part


def email_message_to_mailjet_payload(message: EmailMessage) -> dict[str, Any]:
    from_name, from_email = parseaddr(message.get("From", ""))
    to_name, to_email = parseaddr(message.get("To", ""))
    if not from_email or not to_email:
        raise SmtpSendError(
            "Could not send email",
            reason=SMTP_REASON_MALFORMED_RESPONSE,
        )
    text_part, html_part = _message_text_and_html(message)
    if not text_part and not html_part:
        raise SmtpSendError(
            "Could not send email",
            reason=SMTP_REASON_MALFORMED_RESPONSE,
        )
    entry: dict[str, Any] = {
        "From": {"Email": from_email},
        "To": [{"Email": to_email}],
        "Subject": message.get("Subject", "") or "",
    }
    if from_name:
        entry["From"]["Name"] = from_name
    if to_name:
        entry["To"][0]["Name"] = to_name
    if text_part is not None:
        entry["TextPart"] = text_part
    if html_part is not None:
        entry["HTMLPart"] = html_part
    return {"Messages": [entry]}


def _classify_mailjet_http_status(status_code: int) -> str:
    if status_code in {401, 403}:
        return SMTP_REASON_AUTHENTICATION_FAILURE
    if status_code == 429:
        return SMTP_REASON_RATE_LIMITED
    if status_code in {400, 422}:
        return SMTP_REASON_MESSAGE_REJECTED
    return SMTP_REASON_PROVIDER_ERROR


def _accept_mailjet_response(response: httpx.Response) -> None:
    status_code = response.status_code
    if status_code == 429:
        raise SmtpSendError("Could not send email", reason=SMTP_REASON_RATE_LIMITED)
    if status_code in {401, 403}:
        raise SmtpSendError(
            "Could not send email",
            reason=SMTP_REASON_AUTHENTICATION_FAILURE,
        )
    if status_code < 200 or status_code >= 300:
        raise SmtpSendError(
            "Could not send email",
            reason=_classify_mailjet_http_status(status_code),
        )
    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError):
        raise SmtpSendError(
            "Could not send email",
            reason=SMTP_REASON_MALFORMED_RESPONSE,
        ) from None
    if not isinstance(payload, dict):
        raise SmtpSendError(
            "Could not send email",
            reason=SMTP_REASON_MALFORMED_RESPONSE,
        )
    messages = payload.get("Messages")
    if not isinstance(messages, list) or len(messages) != 1:
        raise SmtpSendError(
            "Could not send email",
            reason=SMTP_REASON_MALFORMED_RESPONSE,
        )
    entry = messages[0]
    if not isinstance(entry, dict):
        raise SmtpSendError(
            "Could not send email",
            reason=SMTP_REASON_MALFORMED_RESPONSE,
        )
    status = entry.get("Status")
    if status == "success":
        return
    if status == "error":
        raise SmtpSendError(
            "Could not send email",
            reason=SMTP_REASON_MESSAGE_REJECTED,
        )
    raise SmtpSendError(
        "Could not send email",
        reason=SMTP_REASON_MALFORMED_RESPONSE,
    )


class MailjetApiTransport:
    """Mailjet HTTPS Send API v3.1. Never retries or falls back to SMTP."""

    def __init__(
        self,
        settings: MailjetSettings | None = None,
        *,
        client: httpx.Client | None = None,
    ):
        self.settings = settings or MailjetSettings()
        self._client = client

    def send(self, message: EmailMessage) -> None:
        self.settings.require_ready()
        payload = email_message_to_mailjet_payload(message)
        try:
            if self._client is not None:
                response = self._post(self._client, payload)
            else:
                with httpx.Client(
                    timeout=_MAILJET_TIMEOUT,
                    verify=True,
                    trust_env=False,
                ) as client:
                    response = self._post(client, payload)
            _accept_mailjet_response(response)
        except SmtpConfigError:
            raise
        except SmtpSendError:
            raise
        except Exception as exc:
            raise SmtpSendError(
                "Could not send email",
                reason=classify_smtp_failure(exc),
            ) from exc

    def _post(self, client: httpx.Client, payload: dict[str, Any]) -> httpx.Response:
        # Single attempt only: ambiguous timeouts must not be retried.
        return client.post(
            self.settings.send_url,
            json=payload,
            auth=(self.settings.api_key, self.settings.secret_key),
            headers={"Content-Type": "application/json"},
        )


class MemoryTransport:
    """In-memory sink for local tests; never logs message bodies."""

    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []
        self.fail_with: Exception | None = None

    def send(self, message: EmailMessage) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.messages.append(message)


class _MisconfiguredTransport:
    """Fails closed when EMAIL_TRANSPORT is not a supported value."""

    def __init__(self, transport_name: str):
        self.transport_name = transport_name
        self.settings = None

    def send(self, message: EmailMessage) -> None:
        raise SmtpConfigError("EMAIL_TRANSPORT must be smtp or mailjet_api")


def selected_email_transport() -> str:
    return (_env("EMAIL_TRANSPORT") or _EMAIL_TRANSPORT_SMTP).lower()


def build_default_transport() -> EmailTransport:
    choice = selected_email_transport()
    if choice == _EMAIL_TRANSPORT_MAILJET_API:
        return MailjetApiTransport()
    if choice == _EMAIL_TRANSPORT_SMTP:
        return SmtpTransport()
    return _MisconfiguredTransport(choice)


def public_app_origin() -> str:
    production = _env("VERVFY_ENVIRONMENT").lower() == "production"
    for name in ("FRONTEND_URL", "SITE_URL", "GOOGLE_FRONTEND_ORIGIN"):
        value = _env(name)
        if value:
            try:
                parsed = urlsplit(value)
                _ = parsed.port
            except ValueError as exc:
                raise SmtpConfigError(f"{name} must be a public origin") from exc
            if (
                parsed.scheme not in {"http", "https"}
                or (production and parsed.scheme != "https")
                or not parsed.netloc
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or parsed.path not in {"", "/"}
            ):
                raise SmtpConfigError(f"{name} must be a public origin")
            return f"{parsed.scheme}://{parsed.netloc}"
    if production:
        raise SmtpConfigError("FRONTEND_URL or SITE_URL is required for password recovery")
    return "http://localhost:3000"


def build_password_reset_message(
    *,
    to_email: str,
    reset_url: str,
    mail_from: str | None = None,
) -> EmailMessage:
    sender = mail_from if mail_from is not None else _env("VERVFY_EMAIL_FROM")
    if not sender:
        raise SmtpConfigError("VERVFY_EMAIL_FROM is required")
    message = EmailMessage()
    message["Subject"] = "Reset your Vervfy password"
    message["From"] = sender
    message["To"] = to_email
    text_body = (
        "We received a request to reset your Vervfy password.\n\n"
        f"Open this link to choose a new password:\n{reset_url}\n\n"
        "This link expires soon and can be used only once. "
        "If you did not request a reset, you can ignore this email.\n"
    )
    html_body = (
        "<p>We received a request to reset your Vervfy password.</p>"
        f'<p><a href="{escape(reset_url, quote=True)}">Choose a new password</a></p>'
        "<p>This link expires soon and can be used only once. "
        "If you did not request a reset, you can ignore this email.</p>"
    )
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    return message


def build_email_verification_message(
    *,
    to_email: str,
    verification_url: str,
    mail_from: str | None = None,
) -> EmailMessage:
    sender = mail_from if mail_from is not None else _env("VERVFY_EMAIL_FROM")
    if not sender:
        raise SmtpConfigError("VERVFY_EMAIL_FROM is required")
    message = EmailMessage()
    message["Subject"] = "Verify your Vervfy email"
    message["From"] = sender
    message["To"] = to_email
    text_body = (
        "We received a request to verify this email address for your Vervfy account.\n\n"
        "Verify that you own this address to continue:\n"
        f"{verification_url}\n\n"
        "This link expires soon and can be used only once. "
        "If you did not request verification, you can ignore this email.\n"
    )
    html_body = (
        "<p>We received a request to verify this email address for your Vervfy account.</p>"
        f'<p><a href="{escape(verification_url, quote=True)}">'
        "Verify your email to continue</a></p>"
        "<p>This link expires soon and can be used only once. "
        "If you did not request verification, you can ignore this email.</p>"
    )
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    return message


def _transport_mail_from(transport: EmailTransport) -> str | None:
    settings = getattr(transport, "settings", None)
    if settings is None:
        return None
    mail_from = getattr(settings, "mail_from", None)
    return mail_from if isinstance(mail_from, str) else None


class EmailSender:
    def __init__(self, transport: EmailTransport | None = None):
        self.transport = transport if transport is not None else build_default_transport()

    def send_password_reset(self, *, to_email: str, token: str) -> None:
        # Token appears only in the recipient message, never in logs.
        reset_url = f"{public_app_origin()}/reset-password#token={token}"
        message = build_password_reset_message(
            to_email=to_email,
            reset_url=reset_url,
            mail_from=_transport_mail_from(self.transport),
        )
        try:
            self.transport.send(message)
        except SmtpConfigError as exc:
            _log_email_delivery_diagnostic(
                "password reset email skipped",
                smtp_failure_reason(exc),
            )
            raise
        except SmtpSendError as exc:
            _log_email_delivery_diagnostic(
                "password reset email failed",
                smtp_failure_reason(exc),
            )
            raise
        except Exception as exc:  # noqa: BLE001 - avoid logging provider or message details
            reason = classify_smtp_failure(exc)
            _log_email_delivery_diagnostic("password reset email failed", reason)
            raise SmtpSendError("Could not send email", reason=reason) from None

    def send_email_verification(self, *, to_email: str, token: str) -> None:
        verification_url = f"{public_app_origin()}/reset-password#verify={token}"
        message = build_email_verification_message(
            to_email=to_email,
            verification_url=verification_url,
            mail_from=_transport_mail_from(self.transport),
        )
        try:
            self.transport.send(message)
        except SmtpConfigError as exc:
            _log_email_delivery_diagnostic(
                "email verification message skipped",
                smtp_failure_reason(exc),
            )
            raise
        except SmtpSendError as exc:
            _log_email_delivery_diagnostic(
                "email verification message failed",
                smtp_failure_reason(exc),
            )
            raise
        except Exception as exc:  # noqa: BLE001 - avoid logging provider or message details
            reason = classify_smtp_failure(exc)
            _log_email_delivery_diagnostic("email verification message failed", reason)
            raise SmtpSendError("Could not send email", reason=reason) from None


def _log_email_delivery_diagnostic(prefix: str, reason: str) -> None:
    safe_reason = _normalize_reason(reason)
    logger.warning(
        "%s: email_reason=%s",
        prefix,
        safe_reason,
        extra={
            "event": "email_delivery_diagnostic",
            "email_reason": safe_reason,
        },
    )


def default_sender(
    transport_factory: Callable[[], EmailTransport] | None = None,
) -> EmailSender:
    if transport_factory is not None:
        return EmailSender(transport_factory())
    return EmailSender()
