# Local Google reauthentication investigation

The observed `freshness_missing_auth_time` followed by `freshness` means the
validated token cannot prove recent authentication. The callback has already
passed token validation, identity lookup and account/session binding; it fails
before account eligibility and proof storage. Login/signup do not require this
claim, explaining why they work.

Installed Authlib 1.9.2 follows this path:
`AsyncOpenIDMixin.parse_id_token` -> joserfc JWT signature verification using
trusted JWKS and allowed algorithms -> `CodeIDToken(token.claims, ...)` ->
claims validation -> `UserInfo(claims)` -> Vervfy `dict(userinfo)`.
`UserInfo` is a dict subclass; its registered profile claims do not restrict
construction. Its optional `filter()` method would remove auth_time, but neither
this parser nor Vervfy calls it. Missing claims are not removed by validation.
Signed local fixtures exercise the real parser with absent, recent and stale
claims. Given the reported diagnostics and this installed code path, the
provider token omits usable auth_time; this is not a parser filtering bug.
No live token was inspected or logged. The OAuth project's settings were not
accessed, so the specific provider-side reason for omission remains unverified.

## Provider contract

Reviewed Google's public documentation during this investigation:

- [OIDC guide](https://developers.google.com/identity/openid-connect/openid-connect):
  auth_time is requested through claims and must be enabled in settings.
  Supported prompt values are none, consent and select_account. max_age is not
  documented as a supported parameter; prompt=login is not listed.
- [Security bundle](https://developers.google.com/identity/siwg/security-bundle):
  setup requires a published, verified app and enabled Session age claims under
  Settings / Advanced Settings. It explicitly says Google does not support
  Google Account reauth requests. auth_time describes the Google session's
  authentication event, not issuance of a token to Vervfy.
- [OIDC Core](https://openid.net/specs/openid-connect-core-1_0.html): max_age
  requires auth_time in the returned ID token. Sending a standard parameter
  does not establish that a particular provider implements it.

## Safe resolution

Keep failing closed when signed auth_time is absent, invalid or older than
300 seconds. Do not replace it with iat, callback time, consent, account selection,
or an existing Vervfy session. Enabling Google's documented claim feature may
supply authentication age, but cannot guarantee a new authentication challenge;
therefore it is not a complete, reliable reauthentication solution.

Proposed alternative: use a previously enrolled Vervfy WebAuthn credential with
user verification required, a server-generated expiring single-use challenge,
strict RP ID/origin and signature verification, and account/session/action binding.
On success issue the existing short-lived one-time action proof using a separate
credential-verification schema, not a fabricated Google auth_time. Password-based
accounts can retain their existing current-password verification.

Google-only accounts without an enrolled credential need an explicitly designed
recovery/bootstrap policy. Do not permit enrollment solely from the stale
session whose freshness is in question. Until such a policy exists, keep these
sensitive operations unavailable when Google cannot prove freshness. A new
recovery or passkey system is a separate implementation, not an OAuth workaround.

At the time of this investigation, no provider settings or authentication
acceptance rules were changed. Existing
local-only diagnostics and Uvicorn callback query redaction remain in place.

## Password-add identity confirmation

The approved password-add design is a narrowly scoped exception to the
`auth_time`-based reauthentication flow. It uses a standard, fully validated
Google OIDC authorization-code transaction with `prompt=select_account`, then
requires the returned issuer and subject to map to the same Google identity
already linked to the active Vervfy account and session. The account-selection
prompt is not treated as fresh Google credential entry.

The server records its own timestamp only after validating the OIDC response
and account/session binding. That timestamp means “Vervfy completed a Google
identity assertion,” not “Google authenticated the user within five minutes.”
It is carried in a separate `google_identity_assertion` proof, bound to the
password-add action, user, session and session version, stored and consumed
once, and expires after 300 seconds. This does not read or substitute `iat` or
`auth_time`. Other sensitive Google actions continue to require a valid
`auth_time` no older than 300 seconds.

Password setup remains limited to an account with no password and a matching
linked Google identity. CSRF, OAuth state/browser binding, PKCE, nonce,
dedicated rate limits, atomic password creation, session-version increment,
and session rotation remain mandatory. This design does not claim to protect
against an attacker who controls the active Google session as well as a Vervfy
session. If future policy requires proof of a recent Google credential-entry
event, Google’s current OIDC behavior cannot provide it reliably; an
independent factor or recovery process is required.
