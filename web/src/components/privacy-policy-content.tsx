"use client";

import LegalDocument from "@/components/legal-document";
import { useLanguage } from "@/lib/i18n";

export default function PrivacyPolicyContent() {
  const { t } = useLanguage();

  return (
    <LegalDocument title="Privacy Policy">
      <section className="credits-source">
        <h2>{t("Who operates Vervfy")}</h2>
        <p>
          {t("Vervfy is an independent project operated by an individual maintainer. For privacy questions or requests, contact the maintainer at")}{" "}
          <a href="mailto:vervfy.dev@proton.me">vervfy.dev@proton.me</a>.
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Information handled by the service")}</h2>
        <p>
          {t("Vervfy processes an internal account ID, username, password hash (not your password), optional email and its verification state, Google account identifier when Google sign-in is used, account creation time, profile and artist photos, uploaded audio and its filename and tags, cover images, lyrics you save, playlists, favorites, and listening history.")}
        </p>
        <p>
          {t("Vervfy supports username/password accounts and Google sign-in. Google sign-in requests OpenID Connect identity, email, and basic profile scopes. Google processes the sign-in request; Vervfy receives the stable Google account identifier and may store an email when Google marks it verified. Vervfy does not receive your Google password, request Gmail or Drive access, or store your Google profile name or photo.")}
        </p>
        <p>
          {t("For username/password accounts, email is optional and is not used to sign in. Password recovery sends a one-time email-verification link to unverified addresses, then a separate reset link. Google-only accounts cannot use password recovery. You can link or unlink Google in account settings. Sensitive actions may require your current password or a fresh Google sign-in.")}
        </p>
        <p>
          {t("The app and its hosting infrastructure also process technical request information, including IP address and browser or network details, to deliver the service, manage sessions, prevent abuse, and apply rate limits. Hosting and service-provider log retention has not been independently verified.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("How information is used and shared")}</h2>
        <p>
          {t("We use account and library information to create and maintain accounts, store and play your library, sync it across devices, and provide requested features. Technical and security information helps keep accounts signed in, protect the service, and limit abusive requests. For password recovery, Vervfy uses the configured SMTP relay to send one-time verification and reset links to the account email. The operator should confirm the applicable legal bases under the LGPD and other relevant law.")}
        </p>
        <p>
          {t("The public website is served from Vercel. The checked project deployment configuration also defines Render application and Redis-compatible key-value services; the app is configured to use Supabase PostgreSQL and private object storage. Those providers process requests, account and library records, session or security data, and uploaded files as needed to provide the service. The live configuration, data regions, and provider log, backup, and retention periods have not been independently verified.")}
        </p>
        <p>
          {t("Optional LRCLIB lookups send track and artist search terms and, where supplied, album or duration metadata or a search query from the app server to LRCLIB. Cover and artist lookups may send track and artist names to MusicBrainz, artist, title, or album metadata to TheAudioDB, or artist names to Wikipedia; some run automatically while resolving artwork or a profile. MusicBrainz and Cover Art Archive also receive server requests to resolve cover art. Uploaded audio files are not sent to these lookup providers. Shared result caches may retain normalized names, provider IDs, URLs, statuses, and timestamps without an account ID. The browser may load images directly from TheAudioDB or Cover Art Archive and fonts from Google Fonts; those providers can receive your IP address and ordinary browser request information.")}
        </p>
        <p>
          {t("Vervfy does not currently configure its own advertising or analytics services. Hosting and service-provider logs may still record technical request data; their retention periods have not been independently verified.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Cookies and browser storage")}</h2>
        <p>
          {t("Vervfy uses an HttpOnly session cookie for up to 30 days; the Secure attribute is enabled when the deployment is HTTPS-only. Google sign-in also uses a temporary security cookie. CSRF tokens protect account actions. When configured, Redis-compatible storage holds session records, temporary rate-limit data, and expiring password-recovery token digests. Choosing a language stores a vervfy-language cookie for one year and saves language and list-view preferences in local storage. LRCLIB lyrics results are cached in local storage; expired entries are removed when accessed, so an unused entry may remain until browser storage is cleared. The service worker caches app shell and static assets, not account API responses.")}
        </p>
        <p>
          {t("Tracks downloaded for offline listening, with optional covers and saved lyrics, are stored in this browser's IndexedDB without automatic expiry. They remain until removed or browser data is cleared. Account deletion attempts to remove this account's offline copies from the browser where deletion was requested; offline copies on other devices are not reachable through that request.")}
        </p>
        <p>
          {t("Account API responses, including profile photos and track covers, use private, no-store cache headers. The service worker does not cache account API responses.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Retention and deletion")}</h2>
        <p>
          {t("Account and library information is kept while your account is active. Account deletion first attempts to invalidate sessions, then requests deletion of account-referenced objects from Supabase Storage, and then attempts to remove the account's primary database records. Failure at a step can leave partial work and require a retry; this is not a promise of immediate physical erasure from provider systems. After a successful server response, the browser attempts to clear cached LRCLIB lyrics and offline data for that account, but this can fail and only affects the browser used for deletion. Shared artwork caches may retain normalized names and result URLs without an account ID; their cleanup period is not verified. Backups and provider logs are outside this flow, and their retention periods have not been confirmed.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Your choices and requests")}</h2>
        <p>
          {t("You can update or remove account information in settings, including an optional email or profile photo, change or add a password, link or unlink Google, and request account deletion. To ask about or exercise rights available under the LGPD and other applicable privacy laws, contact the maintainer at")}{" "}
          <a href="mailto:vervfy.dev@proton.me">vervfy.dev@proton.me</a>.
        </p>
        <p>
          {t("We may ask for information reasonably needed to verify that you control the account. The operator should confirm the controller's legal identity, applicable processing bases, and request procedures with Brazilian privacy counsel. You can also clear browser storage in your browser settings.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Changes to this policy")}</h2>
        <p>
          {t("This notice describes the current implementation and may change as the project develops. Material changes should be reflected here with an updated date.")}
        </p>
      </section>
    </LegalDocument>
  );
}
