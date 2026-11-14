"use client";

import Link from "next/link";
import { LanguageSelect, useLanguage } from "@/lib/i18n";

export default function SiteFooter({ showLanguage = true }: { showLanguage?: boolean }) {
  const { t } = useLanguage();

  return (
    <footer className="site-footer">
      {showLanguage ? <LanguageSelect className="site-footer-language" /> : null}
      <span>© <time suppressHydrationWarning>{new Date().getFullYear()}</time> Vervfy</span>
      <Link href="/privacy">{t("Privacy Policy")}</Link>
      <Link href="/terms">{t("Terms and Conditions")}</Link>
      <Link href="/credits">{t("View credits")}</Link>
    </footer>
  );
}
