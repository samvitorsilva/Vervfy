"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useLanguage } from "@/lib/i18n";
import SiteFooter from "@/components/site-footer";

export default function LegalDocument({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const { language, t } = useLanguage();
  const updatedDate = new Intl.DateTimeFormat(language, {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date("2026-11-13T00:00:00Z"));

  return (
    <main className="credits-page">
      <article className="credits-card legal-document">
        <Link className="credits-back" href="/">← {t("Back to Vervfy")}</Link>
        <h1>{t(title)}</h1>
        <p className="legal-updated">{t("Last updated: {date}").replace("{date}", updatedDate)}</p>
        <p className="legal-draft">
          {t("This document describes the current implementation and is not a certification of legal compliance.")}
        </p>
        {children}
        <SiteFooter />
      </article>
    </main>
  );
}
