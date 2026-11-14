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
| `EMAIL_TRANSPORT` | `smtp` (default) or `mailjet_api`. Use `mailjet_api` on Render Free, which blocks outbound SMTP port 587 |
| `VERVFY_MAILJET_API_KEY` | Mailjet API key (Basic Auth username) when `EMAIL_TRANSPORT=mailjet_api` |
| `VERVFY_MAILJET_SECRET_KEY` | Mailjet secret key (Basic Auth password); keep it in the hosting secret store |
| `VERVFY_SMTP_HOST` | SMTP relay hostname when `EMAIL_TRANSPORT=smtp` |
| `VERVFY_SMTP_PORT` | Relay port; defaults to `587` with STARTTLS, while `465` uses TLS |
| `VERVFY_SMTP_USERNAME` | Relay username; required in production for SMTP |
| `VERVFY_SMTP_PASSWORD` | Relay password; required in production for SMTP, keep it in the hosting secret store |
| `VERVFY_EMAIL_FROM` | Required sender address, e.g. `vervfy.dev@proton.me` |
| `VERVFY_PASSWORD_RECOVERY_ENABLED` | Must be `1` to enable public recovery; defaults to disabled |
| `FRONTEND_URL` | Public frontend origin used for email links; `SITE_URL` is accepted as a fallback |
| `VERVFY_PASSWORD_RESET_TTL_SECONDS` | Token lifetime in seconds; defaults to `1800`, bounded to 60 seconds–24 hours |

The production release sets `VERVFY_PASSWORD_RECOVERY_ENABLED=0`, so recovery
stays disabled until live delivery is verified and the flag is explicitly set
to `1`; recovery routes return `503` while disabled and do not look up accounts
or send messages.

### Render / Mailjet HTTPS API

Render Free blocks outbound SMTP on port 587, so production on that plan must
use the Mailjet HTTPS Send API instead of SMTP:

1. In the Render dashboard for `vervfy-api`, set `EMAIL_TRANSPORT=mailjet_api`.
2. Set `VERVFY_MAILJET_API_KEY` and `VERVFY_MAILJET_SECRET_KEY` from the Mailjet
   account API key pair (secret store only; never commit them).
3. Set `VERVFY_EMAIL_FROM` to the verified sender `vervfy.dev@proton.me`.
4. Keep SMTP variables unset unless you intentionally switch back to
   `EMAIL_TRANSPORT=smtp` on a host that allows outbound 587.

Mailjet requests go to `https://api.mailjet.com/v3.1/send` with Basic Auth,
verified TLS, and a bounded timeout. The client does not retry ambiguous
submissions and does not fall back to SMTP. Delivery is accepted only when the
HTTP response is successful and the per-message `Status` is `success`.

For hosts that allow SMTP, `EMAIL_TRANSPORT=smtp` remains supported with
`in-v3.mailjet.com`, port `587`, the API key as the SMTP username, the secret
key as the SMTP password, and the same verified sender. Production SMTP still
requires authenticated STARTTLS on port 587 and an HTTPS frontend origin. If
delivery is unavailable or cannot send, forgot-password returns the same
generic response and discards the unsent token. Never put Mailjet or SMTP
credentials in `render.yaml` or other tracked files.

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
- Do not log email-link URLs, raw tokens, message bodies, or provider response
  bodies. Diagnostics use fixed reason codes only. Provider and hosting access
  logs should be configured not to capture sensitive query strings.
- Google OAuth, password login, CSRF checks, and session-version invalidation
  remain in the existing auth paths.

## Staging checklist

1. Configure Mailjet API credentials (or SMTP credentials on a host that allows
   port 587) in the hosting dashboard's secret settings, not in the repository
   or deployment YAML. On Render Free, set `EMAIL_TRANSPORT=mailjet_api`.
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
