// Service worker: caches the app shell so capture works with no network.
//
// This is the whole reason Spike A mattered. Without a secure context there is
// no service worker, without a service worker there is no cached shell, and the
// app cannot load offline to write into IndexedDB at all.

const CACHE = "second-shift-shell-v1";
const SHELL = ["/", "/index.html", "/manifest.json", "/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return; // never cache a capture

  const url = new URL(request.url);
  if (url.pathname.startsWith("/entries") || url.pathname.startsWith("/capabilities")) {
    return; // API calls go to the network or fail; a stale capability report misleads
  }

  event.respondWith(
    caches.match(request).then((hit) => hit || fetch(request).catch(() => caches.match("/"))),
  );
});
