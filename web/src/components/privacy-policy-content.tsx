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
          {t("Vervfy is an independent project operated by its individual maintainer, not a registered company. For privacy questions or requests, contact the maintainer at")}{" "}
          <a href="mailto:vervfy.dev@proton.me">vervfy.dev@proton.me</a>.
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Information handled by the service")}</h2>
        <p>
          {t("Vervfy processes an internal account ID, username, password hash, optional email and its verification state, account creation time, profile and artist photos, uploaded audio and its filename and tags, cover images, lyrics you save, playlists, favorites, and listening history.")}
        </p>
        <p>
          {t("The app and its hosting infrastructure also process technical request information, including IP address and browser or network details, to deliver the service, manage sessions, prevent abuse, and apply rate limits. Hosting and service-provider log retention has not been independently verified.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("How information is used and shared")}</h2>
        <p>
          {t("Account and library information is used to authenticate you, store and play your library, sync it across your devices, and provide features such as playlists and listening history. Processing is intended to provide functions you request and to protect the service; the maintainer should confirm and document the legal basis for each operation before broader public or commercial use.")}
        </p>
        <p>
          {t("The deployment uses hosting, database, file-storage, and (where configured) Redis infrastructure, currently including Render and Supabase. Lyrics lookups send track, artist, and sometimes album or duration metadata from the app server to LRCLIB. Artwork and artist lookups can send names from audio tags to MusicBrainz, TheAudioDB, or Wikipedia; some lookups happen automatically when artwork or an artist profile is requested. Your audio files are not sent to these lookup services. Their providers receive the server's request data.")}
        </p>
        <p>
          {t("The browser loads Google Fonts directly and may load third-party artwork directly from TheAudioDB or Cover Art Archive. Those providers can receive your IP address and normal browser request information. Vervfy does not configure advertising or analytics trackers in the inspected app.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Cookies and browser storage")}</h2>
        <p>
          {t("Vervfy uses the auralis_session HttpOnly session cookie for sign-in (up to 30 days; Secure is enabled when HTTPS-only mode is configured). Selecting a language stores a vervfy-language preference cookie for one year and saves the language and list-view preference in local storage. LRCLIB lyrics results are cached in local storage; expired entries are removed when accessed, so an unused entry may remain until browser storage is cleared. The service worker caches app shell and static assets, not account API responses.")}
        </p>
        <p>
          {t("Tracks downloaded for offline listening, with optional covers and saved lyrics, are stored in this browser's IndexedDB without an automatic expiry. They remain until removed from offline storage or browser data is cleared; account deletion attempts to remove that account's offline copies from this browser.")}
        </p>
        <p>
          {t("Account API responses, including profile photos and track covers, use private, no-store cache headers. The service worker does not cache account API responses. Responses cached by an older app version may remain until their previous cache expiry or until browser data is cleared.")}
        </p>
        <p>
          {t("The inspected app has no advertising or analytics cookies, so it currently does not show a cookie-consent banner. Browser storage is used for sign-in, preferences, and the lyrics and offline-download features you request. If non-essential tracking or advertising is added, its legal basis and any required consent must be reviewed before deployment.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Retention and deletion")}</h2>
        <p>
          {t("Account and library information is retained while the account is active. Delete account in account settings removes the account's primary database records and referenced uploaded audio, cover, and artist-photo files from storage. The browser also attempts to clear cached LRCLIB lyrics after successful deletion. Shared artwork lookup caches may retain normalized artist or track names and result URLs without an account ID. Backups, hosting logs, external-provider logs, and expiring infrastructure session or rate-limit entries are outside this deletion flow; their retention periods have not been verified.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Your choices and requests")}</h2>
        <p>
          {t("You can correct your email or remove your profile photo in account settings and delete your account there. To request confirmation of processing, access or a copy of your data, correction of other information, anonymization, blocking or deletion where applicable, information about sharing and the consequences of refusing or withdrawing consent, portability or review of automated decisions where applicable, or to exercise another right under the LGPD, email the maintainer at")}{" "}
          <a href="mailto:vervfy.dev@proton.me">vervfy.dev@proton.me</a>.
        </p>
        <p>
          {t("Requests may require reasonable verification that you control the account. Rights are handled within the scope and exceptions provided by law; information that must be retained by law may be kept only for the required purpose and period. You can also clear browser storage in your browser settings.")}
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
