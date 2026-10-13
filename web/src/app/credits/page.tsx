"use client";

import Link from "next/link";
import { useLanguage } from "@/lib/i18n";

export default function CreditsPage() {
  const { t } = useLanguage();

  return (
    <main className="credits-page">
      <article className="credits-card">
        <Link className="credits-back" href="/">
          ← {t("Back to Vervfy")}
        </Link>
        <p className="credits-eyebrow">VERVFY</p>
        <h1>{t("Credits and data sources")}</h1>
        <p className="credits-intro">{t("Sources, licenses, and how Vervfy uses them.")}</p>

        <section className="credits-source">
          <h2>{t("Artist biographies")}</h2>
          <p>{t("Wikipedia text is shortened or adapted and linked to its article.")}</p>
          <p>{t("Artist photos may be uploaded by you or selected from Wikimedia Commons when the file has a supported open license. Commons copies are stored by Vervfy, credited to their author, linked to their license and file page, and resized for display when needed.")}</p>
          <p className="credits-links">
            <a href="https://www.wikipedia.org/" target="_blank" rel="noopener noreferrer">
              Wikipedia
            </a>
            {" · "}
            <a
              href="https://creativecommons.org/licenses/by-sa/4.0/"
              target="_blank"
              rel="noopener noreferrer"
            >
              CC BY-SA 4.0
            </a>
            {" · "}
            <a href="https://commons.wikimedia.org/" target="_blank" rel="noopener noreferrer">
              Wikimedia Commons
            </a>
          </p>
        </section>

        <section className="credits-source">
          <h2>{t("Lyrics lookup")}</h2>
          <p>{t("LRCLIB supplies optional lyrics lookups. Results are cached only in this browser for three days and are not stored in the Vervfy database.")}</p>
          <p>{t("Lyrics remain subject to the rights held by their respective owners; Vervfy does not claim a reproduction license.")}</p>
          <p className="credits-links">
            <a href="https://lrclib.net/" target="_blank" rel="noopener noreferrer">
              LRCLIB
            </a>
          </p>
        </section>

        <section className="credits-source">
          <h2>{t("User-owned media")}</h2>
          <p>{t("Audio tags, embedded artwork, uploaded covers, and pasted lyrics come from your own files or account.")}</p>
        </section>
      </article>
    </main>
  );
}
