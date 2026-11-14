# Password recovery

Password recovery applies only to accounts with a password and an email address.
Google-only accounts do not receive reset mail. If a password account's email is
unverified, the first message contains a one-time email-verification link; after
the address is verified, a separate one-time reset link is sent. Links expire
after 30 minutes by default. Resetting changes the password, invalidates existing
sessions, and does not sign the user in.

## Configuration

| Variable | Purpose |
| --- | --- |
| `VERVFY_SMTP_HOST` | SMTP relay hostname |
| `VERVFY_SMTP_PORT` | Relay port; defaults to `587` with STARTTLS, while `465` uses TLS |
| `VERVFY_SMTP_USERNAME` | Relay username; required in production |
| `VERVFY_SMTP_PASSWORD` | Relay password; required in production, keep it in the hosting secret store |
| `VERVFY_EMAIL_FROM` | Required sender address, e.g. `vervfy.dev@proton.me` |
| `VERVFY_PASSWORD_RECOVERY_ENABLED` | Must be `1` to enable public recovery; defaults to disabled |
| `FRONTEND_URL` | Public frontend origin used for email links; `SITE_URL` is accepted as a fallback |
| `VERVFY_PASSWORD_RESET_TTL_SECONDS` | Token lifetime in seconds; defaults to `1800`, bounded to 60 seconds–24 hours |

The production release sets `VERVFY_PASSWORD_RECOVERY_ENABLED=0`, so recovery
stays disabled until live delivery is verified and the flag is explicitly set
to `1`; recovery routes return `503` while disabled and do not look up accounts
or send messages. For Mailjet, use `in-v3.mailjet.com`, port `587`, the API key
as the SMTP username, the secret key as the SMTP password, and the verified
sender `vervfy.dev@proton.me`. Production requires authenticated STARTTLS on
port 587 and an HTTPS frontend origin. If SMTP is unavailable or cannot send,
forgot-password returns the same generic response and discards the unsent
token. Never put SMTP credentials in `render.yaml` or other tracked files.

## Security behavior

- Redis stores SHA-256 token digests, not the raw tokens. A new request replaces
  the previous outstanding token for that user.
- Recovery pages use `Referrer-Policy: no-referrer`, `Cache-Control: no-store`,
  do not load third-party scripts, and remove `#token=` / `#verify=` fragments
  from browser history before hydration or analytics can access the URL. The
  one-time token stays in memory only until React submits it.
- The Resend test sender `onboarding@resend.dev` is rejected unless
  `VERVFY_ENVIRONMENT` explicitly identifies a non-production test environment.
  Resend separately limits that sender to authorized recipient addresses; use
  a verified sender domain for production.
- Token claims serialize resets for the same account. A known PostgreSQL
  failure releases the claim for retry; an ambiguous commit keeps it claimed to
  prevent replay. Redis errors fail closed.
- Do not log email-link URLs, raw tokens, or SMTP message bodies. Provider and
  hosting access logs should be configured not to capture sensitive query
  strings.
- Google OAuth, password login, CSRF checks, and session-version invalidation
  remain in the existing auth paths.

## Staging checklist

1. Configure SMTP credentials in the hosting dashboard's secret settings, not
   in the repository or deployment YAML.
2. Set `VERVFY_PASSWORD_RECOVERY_ENABLED=1` only in staging. Keep it `0` in
   production until live delivery has been verified.
3. Set `FRONTEND_URL` to the staging frontend's HTTPS origin. Use
   `onboarding@resend.dev` only for authorized testing; configure a verified
   sender domain for production.
4. Use a synthetic password account and a mailbox controlled by the test team.
   Exercise both an unverified-email account and a verified-email account.
5. Confirm the verification link produces a separate reset message, then reset
   the password and verify old sessions no longer work.
6. Confirm missing accounts and Google-only accounts receive the same API
   response as eligible accounts and no message is sent.
7. Set the recovery flag to `0` after the staging check if staging should not
   send email.

Local tests use an in-memory token store, synthetic accounts, and fake mail
transports. They do not connect to production databases or send external mail.
The feature adds no database migration and must not be validated by running a
hosted migration.
