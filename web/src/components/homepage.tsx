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
  if (sessionStatus === "checking") {
    return (
      <main className="homepage-page homepage-session-check">
        <div className="homepage-content">
          <p className="homepage-session-loading" role="status" aria-busy="true">
            {t("Loading library")}
          </p>
        </div>
      </main>
    );
  }

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
          <section className="landing-hero" aria-labelledby="homepage-title">
            <div className="landing-copy">
              <h1 id="homepage-title">{t("Your personal music library, accessible from anywhere.")}</h1>
              <p className="homepage-tagline">{t("Your music. Your rules.")}</p>
              <p className="homepage-description">
                {t("Upload your music, organize playlists and favorites, and find lyrics and artist details in one place.")}
              </p>
              <div className="homepage-actions">
                <Link className="homepage-cta" href="/register">{t("Create account")}</Link>
                <Link className="homepage-secondary-cta" href="/login">{t("Log in")}</Link>
              </div>
              {sessionStatus === "error" ? (
                <div className="homepage-error" role="alert">
                  <span>{t("Unable to confirm your sign-in status.")}</span>
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
            </div>

            <aside className="homepage-details" aria-label={t("What Vervfy includes")}>
              <ul>
                <li>
                  <h2>{t("Your music library")}</h2>
                  <p>{t("Upload audio files and keep their tags and embedded artwork.")}</p>
                </li>
                <li>
                  <h2>{t("Playlists and playback")}</h2>
                  <p>{t("Make playlists, save favorites, and manage what plays next.")}</p>
                </li>
                <li>
                  <h2>{t("Lyrics and artist details")}</h2>
                  <p>{t("Find more context for the music in your collection.")}</p>
                </li>
              </ul>
            </aside>
          </section>

          <p className="homepage-privacy">
            {t("Each account has its own separate music library.")}{" "}
            <Link href="/privacy">{t("Read the privacy policy")}</Link>
          </p>
        </main>

        <SiteFooter />
      </div>
    </div>
  );
}
