"use client";

import { useEffect } from "react";
import { usePlayerStore, type LibraryView } from "@/store/player-store";

function validView(value: unknown): value is LibraryView {
  if (typeof value !== "string" || value.length > 1000) return false;
  if (["library", "offline", "favorites", "playlists", "recap", "artists", "account"].includes(value)) return true;
  if (/^playlist:[a-zA-Z0-9_-]{1,200}$/.test(value)) return true;
  if (value.startsWith("artist:")) {
    try { return decodeURIComponent(value.slice(7)).trim().length > 0; }
    catch { return false; }
  }
  return false;
}

/** Real browser entries let native back/forward and supported edge gestures work. */
export function useViewHistory() {
  useEffect(() => {
    let restoring = false;
    const initial = new URL(window.location.href).searchParams.get("view");
    if (validView(initial)) usePlayerStore.setState({ view: initial });
    const initialView = usePlayerStore.getState().view;
    window.history.replaceState({ ...window.history.state, vervfyView: initialView }, "");
    const unsubscribe = usePlayerStore.subscribe((state, previous) => {
      if (restoring || state.view === previous.view) return;
      const url = new URL(window.location.href);
      if (state.view === "library") url.searchParams.delete("view");
      else url.searchParams.set("view", state.view);
      window.history.pushState({ ...window.history.state, vervfyView: state.view }, "", url);
    });
    const onBack = (event: PopStateEvent) => {
      const next = event.state?.vervfyView ?? new URL(window.location.href).searchParams.get("view") ?? "library";
      if (!validView(next)) return;
      restoring = true;
      // Updating the store is synchronous; skip transitions when restoring to avoid a history loop.
      usePlayerStore.setState({ view: next });
      restoring = false;
    };
    window.addEventListener("popstate", onBack);
    return () => { unsubscribe(); window.removeEventListener("popstate", onBack); };
  }, []);
}
