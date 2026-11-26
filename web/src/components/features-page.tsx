"use client";

import Link from "next/link";
import Image from "next/image";
import SiteFooter from "@/components/site-footer";
import { useLanguage } from "@/lib/i18n";
import { featuresContent } from "@/lib/features-content";

export default function FeaturesPage() {
  const { language, t } = useLanguage();
  const content = featuresContent[language];
  return (
    <div className="homepage-page features-page">
      <div className="homepage-content">
        <header className="homepage-header">
          <Link className="homepage-brand" href="/" aria-label="Vervfy">
            <Image src="/gemini-svg.svg" alt="" width={32} height={32} />
            <span>Vervfy</span>
          </Link>
          <nav className="homepage-nav" aria-label={t("Main navigation")}>
            <Link className="homepage-login" href="/login">{t("Log in")}</Link>
            <Link className="homepage-signup" href="/register">{t("Create account")}</Link>
          </nav>
        </header>
        <main id="features-content" className="features-main">
          <Link className="credits-back" href="/">← {t("Back to Vervfy")}</Link>
          <div className="features-intro">
            <p className="credits-eyebrow">VERVFY</p>
            <h1>{content.heading}</h1>
            <p>{content.intro}</p>
          </div>
          <div className="features-grid">
            {content.sections.map(([heading, body], index) => (
              <section className="features-section" key={index} aria-labelledby={`feature-${index}`}>
                <h2 id={`feature-${index}`}>{heading}</h2>
                <p>{body}</p>
              </section>
            ))}
          </div>
          <div className="homepage-actions features-actions">
            <Link className="homepage-cta" href="/register">{t("Create account")}</Link>
            <Link className="homepage-secondary-cta" href="/">{t("Back to Vervfy")}</Link>
          </div>
        </main>
        <SiteFooter />
      </div>
    </div>
  );
}
