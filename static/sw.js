const CACHE_NAME = "vervfy-shell-v14";
const SHELL = [
 "/static/index.html",
 "/static/liquid-glass.js?v=1",
 "/static/app.js?v=38",
 "/static/styles.css?v=31",
 "/static/gemini-svg.svg",
];

self.addEventListener("install", event => {
 event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", event => {
 event.waitUntil(
   caches.keys().then(keys => Promise.all(
     keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
   )).then(() => self.clients.claim())
 );
});

self.addEventListener("fetch", event => {
 if(event.request.method !== "GET") return;
 const url = new URL(event.request.url);
 if(url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;
 if(event.request.mode === "navigate") return;
 event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
   const copy = response.clone();
   caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
   return response;
 })));
});
