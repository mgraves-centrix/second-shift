# 0009 — The always-on machine owns the origin

**Status:** accepted · **Date:** 2026-08-30

## Context

The night view was built and served from a development laptop over Tailscale so
it could be looked at. That worked, and it produced a second tailnet origin
running the same capture PWA against a scratch database with a live `POST
/entries`. Nothing distinguished it from the real one in a phone's address bar.

The question it raised: which machine serves, as a rule?

Two prior decisions bear on it without settling it. `CLAUDE.md` states the brain
lives on the always-on machine beside the database, and that a working copy on a
laptop is a clone, never the original. ADR 0003 says compute is a profile rather
than a Spark dependency. The first is about where data lives, the second about
where inference runs. Neither says where the origin lives.

## Decision

**The always-on machine owns the single tailnet origin.** It serves the API and
the exported PWA together, on one origin, as `app.py` already arranges.

A development machine serves on `127.0.0.1` only. It must not hold a tailnet
origin for this project beyond a deliberate, torn-down session.

There is exactly one origin at a time. A second is a defect, not a convenience.

## Consequences

- **The API runs where the brain and the database are.** It shells out to git
  against the brain and writes the database directly. Served from a laptop it
  would read a clone, and the morning interview would write to that clone — a
  divergence discovered weeks later, if at all.

- **Capture keeps working at the hours it exists for.** A service worker needs a
  secure context (Spike A), and that origin has to still resolve at 02:00. A
  sleeping laptop is a lost capture, and the failure is silent: the phone shows
  a page that will not load rather than an error worth acting on.

- **One origin means one database.** Two origins serving the same PWA against
  different databases is how an idea gets written to the wrong place. The PWA
  queues offline and drains on reconnect, so a capture can land in the scratch
  database of a machine that has since been closed.

- **This does not weaken ADR 0003.** Serving host and compute profile are
  separate axes. The origin is pinned to the always-on machine; what runs behind
  it still degrades `spark` → `workstation` → `cloud`. The judge deployment is
  unaffected: it is a container that is its own always-on machine.

- **Cost: the always-on machine must be reachable to demonstrate anything.** A
  laptop-only demonstration is no longer a supported path. Accepted — a product
  whose premise is overnight work cannot be shown honestly on a machine that
  sleeps.

- Tearing a temporary origin down is part of creating it. A `tailscale serve`
  config outlives the process it proxies and will happily point at a dead port.
