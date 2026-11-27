"use client";

export const SESSION_ENDED = "vervfy:session-ended";
const STORAGE_KEY = "vervfy:logout";

// No credentials or account data cross this channel. Storage covers older browsers.
export function endLocalSession(broadcast = true): void {
  window.dispatchEvent(new Event(SESSION_ENDED));
  if (!broadcast) return;
  try {
    const channel = new BroadcastChannel(STORAGE_KEY);
    channel.postMessage("logout");
    channel.close();
  } catch { /* Storage fallback below. */ }
  try { localStorage.setItem(STORAGE_KEY, crypto.randomUUID()); } catch { /* Private mode. */ }
}

export function listenForSessionEnd(callback: () => void): () => void {
  const onStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY && event.newValue) endLocalSession(false);
  };
  let channel: BroadcastChannel | null = null;
  try {
    channel = new BroadcastChannel(STORAGE_KEY);
    channel.onmessage = (event) => {
      if (event.data === "logout") endLocalSession(false);
    };
  } catch { /* Storage events remain available. */ }
  window.addEventListener(SESSION_ENDED, callback);
  window.addEventListener("storage", onStorage);
  return () => {
    channel?.close();
    window.removeEventListener(SESSION_ENDED, callback);
    window.removeEventListener("storage", onStorage);
  };
}
