// Minimal shell cache — proves a service worker can install and serve offline,
// which is what the capture PWA depends on for offline capture.
const CACHE = "spike-a-v1";
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(["./", "./index.html"])));
});
self.addEventListener("fetch", (e) => {
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
});
