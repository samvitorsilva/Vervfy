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
          {t("Vervfy is an independent project operated by its individual maintainer, not a registered company. Questions about these terms can be sent to")}{" "}
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
          {t("Keep your sign-in details secure and provide accurate account information. You are responsible for activity carried out through your account. You may delete your account in account settings; deletion removes the primary account data and referenced stored files, subject to legal retention duties and infrastructure backups or logs described in the Privacy Policy.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Your music and other content")}</h2>
        <p>
          {t("You retain responsibility for the audio, artwork, and lyrics you upload, add, or save. Only add content you are allowed to use and store. You must not use Vervfy to infringe another person’s rights or to break applicable law.")}
        </p>
        <p>
          {t("Vervfy does not claim ownership of your content or grant you rights to third-party content. Lyrics and externally hosted artwork remain subject to the rights and terms of their respective owners and providers.")}
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
      </section>

      <section className="credits-source">
        <h2>{t("Applicable law and rights")}</h2>
        <p>
          {t("These terms do not limit consumer or data-protection rights that apply under mandatory law, including Brazilian law where applicable.")}
        </p>
      </section>

      <section className="credits-source">
        <h2>{t("Changes to these terms")}</h2>
        <p>
          {t("These working terms may change as the project develops. Material changes should be reflected here with an updated date.")}
        </p>
      </section>
    </LegalDocument>
  );
}
