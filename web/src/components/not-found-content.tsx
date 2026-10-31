"use client";

import Link from "next/link";
import SiteFooter from "@/components/site-footer";
import { useLanguage } from "@/lib/i18n";

export default function NotFoundContent() {
  const { t } = useLanguage();

  return (
    <main className="credits-page">
      <article className="credits-card">
        <Link className="credits-back" href="/">← {t("Back to Vervfy")}</Link>
        <p className="credits-eyebrow">VERVFY</p>
        <h1>{t("Page not found")}</h1>
        <p className="credits-intro">{t("The page you’re looking for doesn’t exist or may have moved.")}</p>
        <SiteFooter />
      </article>
    </main>
  );
}
