"use client";

import Link from "next/link";
import Image from "next/image";
import { lazy, Suspense, useEffect, useState } from "react";

// Keep the large private player out of the public landing-page bundle.
const LibraryApp = lazy(() => import("@/components/library-app"));
import { LibraryLoadingScreen } from "@/components/page-loading";
import SiteFooter from "@/components/site-footer";
import { featuresContent } from "@/lib/features-content";
import { useLanguage } from "@/lib/i18n";

type SessionStatus = "checking" | "anonymous" | "authenticated" | "error";

export default function Homepage({ hasSessionCookie = false }: { hasSessionCookie?: boolean }) {
  const { language, t } = useLanguage();
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>(hasSessionCookie ? "checking" : "anonymous");
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

  if (sessionStatus === "checking") return <LibraryLoadingScreen />;

  if (sessionStatus === "authenticated") {
    return (
      <Suspense fallback={<LibraryLoadingScreen />}>
        <LibraryApp />
      </Suspense>
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
              <h1 id="homepage-title">{t("Vervfy — your personal music library, accessible from anywhere.")}</h1>
              <p className="homepage-tagline">{t("Your music. Your rules.")}</p>
              <p className="homepage-description">
                {t("Your personal web music player. Upload your own MP3s, organize playlists and favorites, and listen online or download songs for offline playback.")}
              </p>
              <p><Link className="homepage-secondary-cta" href="/features">{featuresContent[language].link} →</Link></p>
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
                  <p>{t("Upload your own MP3 files with song metadata and embedded album artwork.")}</p>
                </li>
                <li>
                  <h2>{t("Playlists and playback")}</h2>
                  <p>{t("An online MP3 player with playlists, favorites, and downloads for offline listening.")}</p>
                </li>
                <li>
                  <h2>{t("Lyrics and artist details")}</h2>
                  <p>{t("View synchronized or plain lyrics and artist information when available.")}</p>
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
