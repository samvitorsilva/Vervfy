"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect, useState } from "react";
import LibraryApp from "@/components/library-app";
import SiteFooter from "@/components/site-footer";
import { useLanguage } from "@/lib/i18n";

type SessionStatus = "checking" | "anonymous" | "authenticated" | "error";

export default function Homepage() {
  const { t } = useLanguage();
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>("checking");
  const [sessionAttempt, setSessionAttempt] = useState(0);

  useEffect(() => {
    let active = true;

    void fetch("/api/me", { credentials: "same-origin", cache: "no-store" })
      .then((response) => {
        if (!active) return;
        setSessionStatus(
          response.ok
            ? "authenticated"
            : response.status === 401
              ? "anonymous"
              : "error",
        );
      })
      .catch(() => {
        if (active) setSessionStatus("error");
      });

    return () => {
      active = false;
    };
  }, [sessionAttempt]);

  if (sessionStatus === "authenticated") return <LibraryApp />;

  return (
    <div className="homepage-page">
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

        <main className="homepage-main">
          <section className="homepage-hero" aria-labelledby="homepage-title">
            <p className="homepage-eyebrow">{t("Your personal music library.")}</p>
            <h1 id="homepage-title">{t("Your music. Your rules.")}</h1>
            <p className="homepage-description">
              {t("Your personal space for music. Upload your tracks, build playlists, discover lyrics, and listen to your collection—all in one place.")}
            </p>
            <div className="homepage-actions">
              <Link className="homepage-cta" href="/register">{t("Create account")}</Link>
              <Link className="homepage-secondary-cta" href="/login">{t("Log in")}</Link>
            </div>
            {sessionStatus === "error" ? (
              <div className="homepage-error" role="alert">
                <span>{t("We couldn’t check your library right now.")}</span>
                <button
                  type="button"
                  onClick={() => {
                    setSessionStatus("checking");
                    setSessionAttempt((attempt) => attempt + 1);
                  }}
                >
                  {t("Retry connection")}
                </button>
              </div>
            ) : null}
            <p className="homepage-tagline">{t("Your library. Your experience. Vervfy.")}</p>
          </section>
        </main>

        <SiteFooter />
      </div>
    </div>
  );
}
