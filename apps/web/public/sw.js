// Service worker: caches the app shell so capture works with no network.
//
// This is the whole reason Spike A mattered. Without a secure context there is
// no service worker, without a service worker there is no cached shell, and the
// app cannot load offline to write into IndexedDB at all.

const CACHE = "second-shift-shell-v3";
const SHELL = ["/", "/index.html", "/manifest.json", "/icon.svg"];

// Reads whose answer changes every night. Serving a cached one is worse than
// serving nothing: a stale run reads as the current one, with no way to tell.
//
// `/morning` is the API's briefing and `/morning/` is the page that reads it.
// Only a document navigation reaches the page, and navigations are handled
// before this list is consulted, so the bare path here is the API alone.
const LIVE = ["/entries", "/capabilities", "/runs", "/events", "/morning", "/decisions"];

const isLive = (path) => LIVE.some((p) => path === p || path.startsWith(`${p}/`) || path.startsWith(`${p}?`));

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
  if (url.origin !== self.location.origin) return;

  // A document asks for the network first. The shell is the fallback for a
  // page that cannot be reached, which is the offline case this exists for —
  // but only for a document, never for an asset or an API read.
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match(request).then((hit) => hit || caches.match("/"))));
    return;
  }

  // An API read goes straight to the network or fails honestly. Answered from
  // the cache, the briefing came back as the capture shell's HTML with a 200,
  // and the morning screen had no way to know it was not a briefing.
  if (isLive(url.pathname)) return;

  // Everything else is an asset. It may come from the cache, but a miss that
  // cannot be fetched fails as itself.
  //
  // It must never fall back to the shell: returning HTML for a script request
  // does not fail, it *parses* — as a syntax error — so the application never
  // starts and the page is blank with nothing in it explaining why. One dropped
  // request became a permanently white screen that way.
  event.respondWith(caches.match(request).then((hit) => hit || fetch(request)));
});
