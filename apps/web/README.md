# Second Shift — capture PWA

Text capture, offline-tolerant, installable.

```bash
npm --prefix apps/web install
npm --prefix apps/web run build     # static export to apps/web/out
```

`output: "export"` — this builds to files. Serving them needs no second running
process on the Spark, which is one fewer thing that can be down at 2am when an
idea arrives.

Point it at the API with `NEXT_PUBLIC_API_BASE` at build time. Empty means
same-origin, which is what serving the export from the API gives you.

## Why it needs HTTPS

A service worker requires a secure context. Without one there is no cached app
shell, the page cannot load with no network, and offline capture does not exist —
IndexedDB is reachable only once the page has loaded. Tailscale Serve provides
the certificate. See `scripts/spikes/spike-a-secure-context/`.

## The pending count

A count, not a list. It closes the duplicate-tap hole — a user with no feedback
re-taps, and the idempotency key then swallows the duplicate invisibly — while
offering no per-item surface for a retry, edit or delete control to attach to.
`NOT_BUILDING.md` excludes task management, and a visible list of queued items is
one product decision away from being it.

Adding a per-item action crosses that line and needs an explicit override.
