"use client";

import { Suspense, useSyncExternalStore } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import AppLoadingSkeleton from "@/components/app-loading-skeleton";
import { useLanguage } from "@/lib/i18n";
import { validView } from "@/lib/ui/use-view-history";
import { usePlayerStore, type ListMode } from "@/store/player-store";

const subscribe = (listener: () => void) => usePlayerStore.subscribe(listener);
function savedListMode(): ListMode {
  try {
    const saved = localStorage.getItem("vervfy:list-mode");
    if (saved === "list" || saved === "grid") return saved;
  } catch { /* Use the in-memory preference if storage is blocked. */ }
  return usePlayerStore.getState().listMode;
}

function PendingPage() {
  const { t } = useLanguage();
  return <main className="route-skeleton" role="status" aria-label={t("Loading…")} aria-busy="true"><span className="app-skeleton-block app-skeleton-line heading" aria-hidden="true" /></main>;
}

function LibraryShell() {
  const { t } = useLanguage();
  const params = useSearchParams();
  const storedView = usePlayerStore((state) => state.view);
  const listMode = useSyncExternalStore(subscribe, savedListMode, (): ListMode => "grid");
  const requestedView = params.get("view");
  const view = validView(requestedView) ? requestedView : storedView;
  const label = t(view === "account" ? "Loading account…" : view === "recap" ? "Loading your listening history…" : view.startsWith("artist:") ? "Looking up artist details…" : "Loading library");
  return <div id="app" className="app-shell-skeleton">
    <div className="shell">
      <div className="rail" aria-hidden="true" />
      <main className="main"><div className="topbar" aria-hidden="true" /><div className="content"><AppLoadingSkeleton view={view} listMode={listMode} label={label} /></div></main>
    </div>
  </div>;
}

export function LibraryLoadingShell() {
  return <Suspense fallback={<PendingPage />}><LibraryShell /></Suspense>;
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
  if (path === "/" && signedInHint) return <LibraryLoadingShell />;
  if (path === "/") return <main className="homepage-page" role="status" aria-label={t("Loading…")} aria-busy="true"><div className="homepage-content" aria-hidden="true"><header className="homepage-header" /><section className="landing-hero"><div className="landing-copy app-skeleton-public-copy"><span className="app-skeleton-block app-skeleton-public-heading" /><span className="app-skeleton-block app-skeleton-line" /><span className="app-skeleton-block app-skeleton-line" /><span className="app-skeleton-block app-skeleton-profile-button" /></div></section></div></main>;
  return <main className="route-skeleton app-skeleton-document" role="status" aria-label={t("Loading…")} aria-busy="true"><div aria-hidden="true"><span className="app-skeleton-block app-skeleton-line heading" />{Array.from({ length: 5 }, (_, index) => <section key={index}><span className="app-skeleton-block app-skeleton-line short" /><span className="app-skeleton-block app-skeleton-line" /><span className="app-skeleton-block app-skeleton-line" /></section>)}</div></main>;
}
