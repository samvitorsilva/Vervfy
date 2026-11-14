"""Internal lookup boundary; never expose directly as a public API.

The caller MUST first validate the Google OIDC token and one-time browser-bound
transaction. This helper does not verify Google claims or authenticate a user.
Use a dedicated backend connection granted vervfy_identity_lookup, not a broad
owner/superuser connection. Possession of that capability is a trust boundary.
"""
from sqlalchemy import text
from sqlalchemy.engine import Connection


def lookup_verified_google_identity(
    connection: Connection, *, issuer: str, subject: str,
) -> str | None:
    """Return only the owner ID of an exact, already-verified Google identity.

    No email argument, wildcard search, normalization, linking, or writes.
    Missing database privilege propagates as an error; never fall back to a
    direct table query. No production caller exists until OIDC is implemented.
    """
    if issuer not in ('https://accounts.google.com', 'accounts.google.com'):
        raise ValueError('Unexpected verified Google issuer')
    if not isinstance(subject, str) or not 1 <= len(subject) <= 255 or '\x00' in subject:
        raise ValueError('Invalid verified Google subject')
    if connection.dialect.name != 'postgresql':
        raise RuntimeError('Provider identity lookup requires PostgreSQL privileges')
    return connection.execute(
        text('SELECT vervfy_auth.lookup_provider_identity(:issuer, :subject)'),
        {'issuer': issuer, 'subject': subject},
    ).scalar_one_or_none()
