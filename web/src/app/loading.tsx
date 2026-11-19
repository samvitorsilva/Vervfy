"use client";

import { useLanguage } from "@/lib/i18n";

/** A small streaming boundary also lets Next prefetch a useful loading shell. */
export default function LoadingPage() {
  const { t } = useLanguage();
  return <main className="route-skeleton" role="status" aria-label={t("Loading…")} aria-busy="true">
    <div aria-hidden="true">
      <span className="app-skeleton-block app-skeleton-line heading" />
      <span className="app-skeleton-block app-skeleton-line" />
      <div className="route-skeleton-grid">{Array.from({ length: 6 }, (_, index) => <div className="route-skeleton-card" key={index}>
        <span className="app-skeleton-block route-skeleton-image" />
        <span className="app-skeleton-block app-skeleton-line" />
        <span className="app-skeleton-block app-skeleton-line short" />
      </div>)}</div>
    </div>
  </main>;
}
