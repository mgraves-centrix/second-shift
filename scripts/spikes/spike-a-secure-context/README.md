# Spike A — secure context over Tailscale Serve

**Question:** does Tailscale Serve give a phone a valid-TLS origin that produces
a secure context, so a service worker registers?

**Answer: yes.** All six checks passed on an iPhone, 2026-08-27.

## Why it mattered

Service workers require a secure context. Without one there is no cached app
shell, so the PWA cannot load with no network — and `capture`'s "succeeds
without a network" requirement is unbuildable. IndexedDB works over plain HTTP,
but only once the page has loaded, which is exactly what fails.

The earlier assumption that "text capture needs no HTTPS" was true about the
microphone and wrong about the PWA.

## Result

| Check | Result |
|---|---|
| `location.protocol` is `https:` | PASS |
| `window.isSecureContext` | PASS |
| `navigator.serviceWorker` exists | PASS |
| IndexedDB available | PASS |
| `navigator.mediaDevices.getUserMedia` | PASS |
| **Service worker registers** | **PASS** — scope `https://<host>.<tailnet>.ts.net/` |

Certificate: Let's Encrypt, `CN=<host>.<tailnet>.ts.net`, valid to
26 Nov 2026, validating with no override.

`getUserMedia` passing was not the question asked, but it answers the
microphone half of the original spike at the same time.

## Reproducing

Requires `sudo tailscale set --operator=$USER` once, and HTTPS Certificates
enabled for the tailnet in the admin console.

```bash
tailscale serve --bg --https=443 /path/to/this/directory
```

Then open the tailnet hostname on a phone. `tailscale serve --https=443 off`
to stop.

Kept rather than deleted: if TLS regresses, or when Serve is repointed at the
capture API, this re-answers the question in one page load.
