const CACHE_NAME = "vervfy-next-shell-v3";
const SHELL_ASSETS = [
  "/offline.html",
  "/manifest.webmanifest",
  "/gemini-svg.svg",
];
const STATIC_CACHE_PREFIX = "vervfy-next-shell-";

function isExcludedRequest(request, url) {
  return (
    request.method !== "GET" ||
    url.origin !== self.location.origin ||
    url.pathname === "/api" ||
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/backend-auth/") ||
    url.pathname === "/logout" ||
    request.headers.has("range") ||
    ["audio", "video"].includes(request.destination) ||
    /\/(?:stream|audio)(?:\/|$)/i.test(url.pathname)
  );
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith(STATIC_CACHE_PREFIX) && key !== CACHE_NAME)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (isExcludedRequest(request, url)) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(async () => {
        const offlinePage = await caches.match(
          new URL("/offline.html", self.location.origin).href,
        );
        return offlinePage ?? Response.error();
      }),
    );
    return;
  }

  const isStaticAsset =
    url.pathname.startsWith("/_next/static/") ||
    SHELL_ASSETS.includes(url.pathname);
  if (!isStaticAsset) return;

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((response) => {
        const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
        if (
          response.ok &&
          response.type === "basic" &&
          !contentType.startsWith("audio/") &&
          !contentType.startsWith("video/")
        ) {
          const copy = response.clone();
          return caches.open(CACHE_NAME).then((cache) =>
            cache.put(request, copy).then(() => response),
          );
        }
        return response;
      });
    }),
  );
});
