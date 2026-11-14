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
          {t("Vervfy is operated by Sam Vitor. This operator identification is provisional and must be confirmed before launch. For privacy questions or requests, email")}{" "}
          <a href="mailto:vervfy.dev@proton.me">vervfy.dev@proton.me</a>.
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Information handled by the service")}</h2>
        <p>
          {t("Vervfy processes the information needed to provide your account and music library. This can include your username, password verifier, optional email address, profile photo, uploaded audio, audio tags, cover art, lyrics you save, playlists, favorites, and listening history.")}
        </p>
        <p>
          {t("The service also receives standard request information, such as your IP address, when needed to operate sessions, protect the service, and apply rate limits.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("How information is used and shared")}</h2>
        <p>
          {t("Account and library information is used to authenticate you, store and play your library, sync it across your devices, and provide library features such as listening history.")}
        </p>
        <p>
          {t("Vervfy uses database and file-storage infrastructure to operate accounts and store uploaded files. When you use optional lyrics and artwork features, relevant track or artist search terms may be sent to LRCLIB, TheAudioDB, MusicBrainz, Cover Art Archive, or Wikipedia. Images hosted by third parties may be loaded directly from those providers. Your audio files are not sent to these lookup providers.")}
        </p>
        <p>
          {t("Lyrics returned by LRCLIB are cached in your browser for up to three days. Interface preferences and language settings may also be stored in your browser. Vervfy uses a session cookie to keep you signed in and a language preference cookie when you select a language.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Retention and deletion")}</h2>
        <p>
          {t("Account information and library content are retained while your account is active. You can request deletion using Delete account in account settings. The deletion flow removes the account and its associated library records and stored files. Browser caches can be cleared separately through your browser settings.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Your choices and requests")}</h2>
        <p>
          {t("You can update or remove account information in account settings, delete your account, and clear local browser storage through your browser. For privacy requests, contact")}{" "}
          <a href="mailto:vervfy.dev@proton.me">vervfy.dev@proton.me</a>.
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Changes to this policy")}</h2>
        <p>
          {t("This draft may change before launch. The published policy should show its effective date and explain material changes.")}
        </p>
      </section>
    </LegalDocument>
  );
}
