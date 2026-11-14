"use client";

import LegalDocument from "@/components/legal-document";
import { useLanguage } from "@/lib/i18n";

export default function TermsContent() {
  const { t } = useLanguage();

  return (
    <LegalDocument title="Terms and Conditions">
      <section className="credits-source">
        <h2>{t("Operator and privacy")}</h2>
        <p>
          {t("Vervfy is an independent project operated by an individual maintainer. Questions about these terms can be sent to")}{" "}
          <a href="mailto:vervfy.dev@proton.me">vervfy.dev@proton.me</a>.
        </p>
        <p>
          <a href="/privacy">{t("Privacy Policy")}</a>{" "}
          {t("explains what information Vervfy handles, how to make a privacy request, and how account deletion works.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Your account")}</h2>
        <p>
          {t("You may register only if you are legally permitted to accept these Terms and use the service; Vervfy does not currently perform age verification. Provide accurate account information and protect your sign-in details. The service supports username/password accounts and Google sign-in. Email is optional for password accounts and is not used to sign in; email verification and email-based recovery are not implemented.")}
        </p>
        <p>
          {t("Google-only accounts must add a password before unlinking Google. You are responsible for activity carried out through your account. Sensitive actions may require your current password or a fresh Google sign-in. You may delete your account in account settings. The deletion flow attempts to invalidate sessions, delete account-referenced stored files, and remove primary account records; errors may require a retry. It does not guarantee immediate physical erasure from provider backups or logs or remove offline copies from every device. See the Privacy Policy.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Your music and other content")}</h2>
        <p>
          {t("Vervfy is a personal music-library tool for audio you upload; it does not provide a licensed music catalogue. You are responsible for ensuring you have the rights or permissions needed to upload, store, sync, play offline, and use audio, artwork, metadata, or lyrics. Do not upload or use content in a way that infringes another person's rights or violates applicable law.")}
        </p>
        <p>
          {t("You retain ownership of your content. Vervfy uses it to provide your library but does not claim ownership or grant rights to third-party material. Third-party lyrics and artwork remain subject to their own terms and rights; Vervfy does not represent that it has commercial licenses or permissions from those providers or rights holders.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Third-party services and offline playback")}</h2>
        <p>
          {t("Optional lyrics, artwork, and artist-information features depend on LRCLIB, MusicBrainz, Cover Art Archive, TheAudioDB, and Wikipedia as described in the Privacy Policy. They may change terms, limit requests, return inaccurate or unavailable results, or stop service. Vervfy does not control these providers, guarantee their output, or claim a license to content they supply. You must respect applicable provider terms and rights.")}
        </p>
        <p>
          {t("Offline playback may store audio and related cover art or lyrics in this device's browser storage. Use those copies only as permitted by the rights applicable to the content. Browser storage can be cleared or unavailable, and account deletion may not reach offline copies on other devices; manage those copies in each browser.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Acceptable use")}</h2>
        <p>
          {t("Do not attempt to disrupt, damage, reverse engineer, or gain unauthorized access to Vervfy or its infrastructure. Do not use the service to upload malicious content or interfere with another person’s use of the service.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Service availability")}</h2>
        <p>
          {t("Vervfy may change, suspend, or discontinue features to maintain or protect the service. Third-party lookup and media services are outside Vervfy’s control and may be unavailable or change their responses.")}
        </p>
        <p>
          {t("Vervfy may restrict or suspend an account when reasonably necessary to protect the service, address misuse, or comply with law. If you cannot access your account to delete it, contact the maintainer.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Applicable law and rights")}</h2>
        <p>
          {t("These Terms must be read with laws that apply to you. Nothing here limits mandatory consumer or data-protection rights under Brazilian law, including the LGPD, when those rules apply.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Changes to these terms")}</h2>
        <p>
          {t("We may update these Terms as the service changes. The date above shows the latest revision. Any notice or consent required by applicable law will be provided.")}
        </p>
      </section>
    </LegalDocument>
  );
}
