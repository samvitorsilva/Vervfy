"use client";

import { apiFetch, expectOk } from "@/lib/api/client";

// Keep signed capabilities in memory only. Never persist or log a lease.
export class AudioLease {
  private lease: { url: string; deadline: number } | null = null;
  private pending: Promise<string> | null = null;
  private timer: number | null = null;
  private abort = new AbortController();
  private disposed = false;
  private inlineSource: string | null = null;

  constructor(private readonly endpoint: string) {
    const url = new URL(endpoint, window.location.href);
    if (url.origin !== window.location.origin || !/^\/api\/tracks\/[^/]+\/playback-lease$/.test(url.pathname) || url.search || url.hash) {
      throw new Error("Invalid playback lease endpoint");
    }
  }

  async source(): Promise<string> {
    if (this.disposed) throw new DOMException("Playback cancelled", "AbortError");
    if (this.inlineSource) return this.inlineSource;
    if (this.lease && this.lease.deadline - performance.now() > 120_000) return this.lease.url;
    if (this.pending) return this.pending;
    const started = performance.now();
    const requestAbort = new AbortController();
    const onAbort = () => requestAbort.abort();
    this.abort.signal.addEventListener("abort", onAbort, { once: true });
    const timeout = window.setTimeout(() => requestAbort.abort(), 10_000);
    this.pending = (async () => {
      const response = await apiFetch(this.endpoint, {
        cache: "no-store", signal: requestAbort.signal,
      });
      if (response.status === 409) {
        // Legacy audio stays on the authenticated application Range endpoint.
        // Never downgrade authentication errors to a redirect or public source.
        if (this.disposed) throw new DOMException("Playback cancelled", "AbortError");
        this.inlineSource = new URL(this.endpoint, window.location.href).href.replace(/\/playback-lease$/, "/stream");
        return this.inlineSource;
      }
      await expectOk(response);
      const data: unknown = await response.json();
      if (!data || typeof data !== "object" || !("url" in data) || typeof data.url !== "string" ||
          !("expiresAt" in data) || typeof data.expiresAt !== "number" ||
          !("serverTime" in data) || typeof data.serverTime !== "number") {
        throw new Error("Invalid playback lease");
      }
      const url = new URL(data.url, window.location.href);
      const validity = (data.expiresAt - data.serverTime) * 1000;
      if (!Number.isFinite(validity) || validity <= 120_000 || validity > 901_000 ||
          url.username || url.password || url.hash ||
          (url.protocol !== "https:" && !(window.location.hostname === "127.0.0.1" && url.hostname === "127.0.0.1")) ||
          !url.pathname.startsWith("/storage/v1/object/sign/")) {
        throw new Error("Invalid playback lease");
      }
      const deadline = started + Math.min(validity, 900_000);
      if (this.disposed || deadline - performance.now() <= 120_000) throw new Error("Playback lease unavailable");
      this.lease = { url: url.href, deadline };
      this.schedule();
      return url.href;
    })().finally(() => {
      window.clearTimeout(timeout);
      this.abort.signal.removeEventListener("abort", onAbort);
      this.pending = null;
    });
    return this.pending;
  }

  warm(): void {
    // A failed proactive request leaves a healthy native stream alone. On demand,
    // the controller applies its bounded retry policy. apiFetch handles 401 teardown.
    void this.source().catch(() => {
      if (!this.disposed) this.schedule(30_000);
    });
  }

  invalidate(): void { this.lease = null; this.inlineSource = null; }

  dispose(): void {
    this.disposed = true;
    this.abort.abort();
    if (this.timer !== null) window.clearTimeout(this.timer);
    this.timer = null;
    this.lease = null;
    this.inlineSource = null;
  }

  private schedule(retryDelay?: number): void {
    if (this.timer !== null) window.clearTimeout(this.timer);
    const delay = retryDelay ?? Math.max(1000, (this.lease?.deadline ?? 0) - performance.now() - 120_000);
    this.timer = window.setTimeout(() => { this.timer = null; this.warm(); }, delay);
  }
}
