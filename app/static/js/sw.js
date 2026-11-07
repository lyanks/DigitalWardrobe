// The service worker: a small script the browser keeps running for this
// site. It's what lets phones install Digital Wardrobe as an app.
//
// It keeps it simple on purpose:
// - pages always come from the server (your data is never stale);
// - if you're offline, you get a friendly "You're offline" page;
// - CSS, JS, fonts and icons are kept in a cache, so the app opens fast.
// Bump VERSION after changing this file, so old caches are thrown away.
const VERSION = "v1";
const CACHE = `wardrobe-${VERSION}`;
const OFFLINE = "/static/offline.html";

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.add(OFFLINE)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)),
    )),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;  // forms and uploads go straight through

  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE)));
    return;
  }
  const url = new URL(request.url);
  if (url.origin === location.origin && url.pathname.startsWith("/static/")) {
    // Show the saved copy at once, and refresh it in the background.
    event.respondWith(caches.open(CACHE).then(async (cache) => {
      const saved = await cache.match(request);
      const fresh = fetch(request).then((response) => {
        if (response.ok) cache.put(request, response.clone());
        return response;
      }).catch(() => saved);
      return saved || fresh;
    }));
  }
});
