"""Transactional email via SMTP using VERVFY_SMTP_* environment variables."""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from collections.abc import Callable
from email.message import EmailMessage
from email.utils import parseaddr
from html import escape
from typing import Protocol
from urllib.parse import urlsplit

logger = logging.getLogger("vervfy.email")


class EmailTransport(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class SmtpConfigError(RuntimeError):
    """SMTP is not configured for outbound mail."""


class SmtpSendError(RuntimeError):
    """SMTP relay rejected or failed the message."""


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


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
        sender = parseaddr(self.mail_from)[1].lower()
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
        except Exception as exc:
            raise SmtpSendError("Could not send email") from exc


class MemoryTransport:
    """In-memory sink for local tests; never logs message bodies."""

    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []
        self.fail_with: Exception | None = None

    def send(self, message: EmailMessage) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.messages.append(message)


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


class EmailSender:
    def __init__(self, transport: EmailTransport | None = None):
        self.transport = transport or SmtpTransport()

    def send_password_reset(self, *, to_email: str, token: str) -> None:
        # Token appears only in the recipient message, never in logs.
        reset_url = f"{public_app_origin()}/reset-password#token={token}"
        settings = getattr(self.transport, "settings", None)
        mail_from = settings.mail_from if isinstance(settings, SmtpSettings) else None
        message = build_password_reset_message(
            to_email=to_email,
            reset_url=reset_url,
            mail_from=mail_from,
        )
        try:
            self.transport.send(message)
        except SmtpConfigError:
            logger.warning("password reset email skipped: SMTP is not configured")
            raise
        except SmtpSendError:
            logger.warning("password reset email failed: SMTP provider error")
            raise
        except Exception:  # noqa: BLE001 - avoid logging provider or message details
            logger.warning("password reset email failed: unexpected transport error")
            raise SmtpSendError("Could not send email") from None

    def send_email_verification(self, *, to_email: str, token: str) -> None:
        verification_url = f"{public_app_origin()}/reset-password#verify={token}"
        settings = getattr(self.transport, "settings", None)
        mail_from = settings.mail_from if isinstance(settings, SmtpSettings) else None
        message = build_email_verification_message(
            to_email=to_email,
            verification_url=verification_url,
            mail_from=mail_from,
        )
        try:
            self.transport.send(message)
        except SmtpConfigError:
            logger.warning("email verification message skipped: SMTP is not configured")
            raise
        except SmtpSendError:
            logger.warning("email verification message failed: SMTP provider error")
            raise
        except Exception:  # noqa: BLE001 - avoid logging provider or message details
            logger.warning("email verification message failed: unexpected transport error")
            raise SmtpSendError("Could not send email") from None


def default_sender(
    transport_factory: Callable[[], EmailTransport] | None = None,
) -> EmailSender:
    if transport_factory is not None:
        return EmailSender(transport_factory())
    return EmailSender()
