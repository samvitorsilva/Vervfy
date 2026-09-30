const CACHE_NAME = "vervfy-shell-v17";
// Keep these asset versions in sync with static/index.html.
const SHELL = [
 "/",
 "/static/liquid-glass.js?v=4",
 "/static/app.js?v=41",
 "/static/styles.css?v=37",
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
 if(event.request.mode === "navigate" && url.pathname === "/"){
   event.respondWith(fetch(event.request).then(response => {
     if(response.ok){
       const copy = response.clone();
       caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
     }
     return response;
   }).catch(() => caches.match(event.request)));
   return;
 }
 event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
   if(!response.ok) return response;
   const copy = response.clone();
   caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
   return response;
 })));
});

self.addEventListener("message", event => {
 if(event.data?.type !== "clear-shell") return;
 event.waitUntil(caches.open(CACHE_NAME).then(cache =>
   cache.keys().then(keys => Promise.all(keys
     .filter(request => new URL(request.url).pathname === "/")
     .map(request => cache.delete(request))
   ))
 ));
});
