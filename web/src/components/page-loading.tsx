"use client";

import Image from "next/image";
import { usePathname } from "next/navigation";
import { useLanguage } from "@/lib/i18n";

export function LibraryLoadingScreen() {
  const { t } = useLanguage();
  return (
    <main className="homepage-page homepage-transition" role="status" aria-label={t("Loading your music library")} aria-live="polite" aria-busy="true">
      <div className="homepage-transition-inner">
        <div className="homepage-transition-brand">
          <div className="homepage-transition-mark" aria-hidden="true">
            <Image src="/gemini-svg.svg" alt="" width={72} height={72} priority />
          </div>
          <span className="homepage-transition-name">Vervfy</span>
        </div>
        <div className="homepage-transition-status">
          <div className="homepage-transition-progress" aria-hidden="true"><span /></div>
          <span className="homepage-transition-caption">{t("Loading your music library")}</span>
        </div>
      </div>
    </main>
  );
}

export default function PageLoading({ signedInHint = false }: { signedInHint?: boolean }) {
  const path = usePathname();
  const { t } = useLanguage();
  if (["/login", "/register", "/forgot-password", "/reset-password"].includes(path)) {
    const fields = path === "/register" ? 3 : path === "/login" ? 2 : 1;
    return <main className="auth-page" role="status" aria-label={t("Loading…")} aria-busy="true"><section className="auth-card app-skeleton-auth" aria-hidden="true">
      <span className="app-skeleton-block app-skeleton-auth-brand" /><span className="app-skeleton-block app-skeleton-line heading" /><span className="app-skeleton-block app-skeleton-line" />
      {Array.from({ length: fields }, (_, index) => <div className="app-skeleton-auth-field" key={index}><span className="app-skeleton-block app-skeleton-line short" /><span className="app-skeleton-block app-skeleton-auth-input" /></div>)}
      <span className="app-skeleton-block app-skeleton-auth-input" />
    </section></main>;
  }
  if (path === "/" && signedInHint) return <LibraryLoadingScreen />;
  if (path === "/") return <main className="homepage-page" role="status" aria-label={t("Loading…")} aria-busy="true"><div className="homepage-content" aria-hidden="true"><header className="homepage-header" /><section className="landing-hero"><div className="landing-copy app-skeleton-public-copy"><span className="app-skeleton-block app-skeleton-public-heading" /><span className="app-skeleton-block app-skeleton-line" /><span className="app-skeleton-block app-skeleton-line" /><span className="app-skeleton-block app-skeleton-profile-button" /></div></section></div></main>;
  return <main className="route-skeleton app-skeleton-document" role="status" aria-label={t("Loading…")} aria-busy="true"><div aria-hidden="true"><span className="app-skeleton-block app-skeleton-line heading" />{Array.from({ length: 5 }, (_, index) => <section key={index}><span className="app-skeleton-block app-skeleton-line short" /><span className="app-skeleton-block app-skeleton-line" /><span className="app-skeleton-block app-skeleton-line" /></section>)}</div></main>;
}
