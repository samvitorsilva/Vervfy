"""Account mutations for the gated passkey routes.

Caller consumes the exact action proof in this same tenant transaction, then
rotates sessions only after commit. These helpers never commit or authorize.
"""

import hmac

import sqlalchemy as sa

import auth
from db import User
from passkeys import PasskeyError, _tenant


def set_password(session, binding, password, *, expected_password_hash):
    _tenant(session, binding)
    if binding.action != "password_add":
        raise PasskeyError("Unsupported password action")
    error = auth.validate_password(password)
    if error:
        raise ValueError(error)
    row = session.scalar(
        sa.select(User).where(User.id == binding.user_id).with_for_update()
    )
    if (
        row.password_hash != expected_password_hash
        or expected_password_hash is not None
    ):
        raise PasskeyError("Password creation no longer eligible")
    row.password_hash = auth.hash_password(password)
    row.session_version += 1
    session.flush()
    return row.session_version


def change_email(session, binding, email):
    _tenant(session, binding)
    if binding.action != "email_change":
        raise PasskeyError("Email action required")
    email = email.strip().lower() or None
    if email and auth.validate_email(email):
        raise ValueError("Invalid email")
    row = session.scalar(
        sa.select(User).where(User.id == binding.user_id).with_for_update()
    )
    row.email = email
    row.email_verified = False
    row.pending_email = None
    row.session_version += 1
    session.flush()  # Unique email constraint; any failure must roll back caller tx.
    return row.session_version


def bump_logout_version(session, binding):
    _tenant(session, binding)
    if not hmac.compare_digest(binding.action, "logout_all"):
        raise PasskeyError("Logout action required")
    row = session.scalar(
        sa.select(User).where(User.id == binding.user_id).with_for_update()
    )
    row.session_version += 1
    session.flush()
    return row.session_version
