# API layer prompt

Paste as the first message of a fresh session. Entirely local — no Spark, no
tailnet, no credentials.

**Run this early. It is a refactor that removes a collision, and every session
that adds a route is cheaper after it and serialized before it.**

---

Build out the API layer. Read `openspec/constitution.md`, `CLAUDE.md`,
`docs/ARCHITECTURE.md` and `docs/SPEC_ROADMAP.md` first; they are the rules, not
background.

## Why this one, and why early

`apps/api/secondshift/api/app.py` is **one 368-line file** holding every route,
the context factory, the response mappers and the static mount.
`docs/ARCHITECTURE.md` specifies `api/routes/` in its own directory tree. **It
does not exist.**

That is a scheduling problem, not a tidiness one. Five of the sessions in
`00_INDEX.md` need to add routes: `MORNING_INTERVIEW` (decisions and answers),
`ARTIFACTS` (serving files), `NIGHT_PIPELINE` (run on demand), `JUDGE_MODE` (run
the night), and `NEBIUS_EXECUTOR` (telemetry ingest). All five would edit the
same file. **Until this lands, `api/app.py` is a third collision surface and the
index was wrong to name only two.**

Do this first and those five become parallel. Do it late and they queue.

## What already exists — do not invent any of it

- Six routes: `GET /health`, `GET /capabilities`, `POST /entries`,
  `GET /runs`, `GET /runs/{run_id}/timeline`, `GET /events/{event_id}`.
- `Context` — a frozen-ish dataclass carrying `repo`, `recorder`, `profile`,
  `report`, `is_synthetic` — built once at startup by `build_context(db_path,
  is_synthetic=, profile=)` and injected with `Depends(get_context)`.
- `create_app(context)` returns the `FastAPI` app. Tests build a `Context`
  directly and wrap it in `TestClient`; that pattern is load-bearing and there
  are 40+ tests relying on it.
- `schemas.py`, 214 lines of Pydantic response models, several carrying comments
  explaining what they deliberately **do not** contain — `TimelineEventResponse`
  has no payload field, `EventDetailResponse` has no field prompt or completion
  text could travel in. Those absences are the contract; preserve them.
- **The static mount is last, on purpose**, so every API route matches first:
  `app.mount("/", StaticFiles(directory=WEB_EXPORT, html=True))`. Move it and the
  PWA silently swallows the API.
- `main.py` reads `SECOND_SHIFT_DB` and `SECOND_SHIFT_SYNTHETIC`, and the latter
  is **server-derived, never accepted from a request**.
- Two migrations: `0001_initial.sql` and `0002_capture.sql`.

## The open decision

**Whether the API gets authentication, and when.**

Today there is none, and that is currently correct: it binds `127.0.0.1`, it is
single-tenant by design, `NOT_BUILDING.md` excludes accounts, and it reaches the
phone through `tailscale serve` rather than the public internet.

That changes the moment `nebius-executor` adds an inbound ingest route, which is
the first path where something *not on the machine* talks to it. The
`nebius-executor` design has an open marker on exactly this.

**Do not decide this by preference and do not build an auth framework
speculatively.** Decide the *shape*: whether authentication is a per-route
concern this layer must support, or a single ingest-only concern that belongs
entirely to that capability. Write down what each choice costs when the marker
resolves either way, and put it in the proposal.

The second open thing: **versioning.** The only consumer today is a PWA shipped
from the same repository in the same deploy, which is a strong argument against
`/v1`. The ingest route would have an external consumer, which is an argument
for it. Decide with those two facts, not with convention.

## What good looks like

- One module per capability under `api/routes/`, and **adding a route means
  adding or touching one file**. That is the whole measure of success.
- Every existing route returns **byte-identical** responses. This is a refactor;
  a behavior change here is a bug, not an improvement.
- The static mount is still last, and something fails loudly if it is not.
- The error shape is consistent, and a 404 says which thing was not found.
- `Context` and `create_app` keep their signatures, so the 40+ tests that build a
  context directly keep working unchanged.
- A new contributor can find where a route lives from its path alone.

## Scope — what NOT to build

- **No auth framework.** Decide the shape; build it when the marker resolves.
- **No API versioning** unless the decision above says so.
- **No ORM, no GraphQL, no serializer library.** Pydantic and FastAPI.
- **No new response envelope.** Wrapping every payload in `{data: ...}` is a
  breaking change to a working PWA for no benefit.
- **No new routes.** This moves what exists. A capability adds its own.
- **No rate limiting, no CORS.** Same origin by construction.

## Constitution hooks

- **Principle 5.** One codebase, two deployments. Nothing here may branch on
  which instance is running; the judge instance differs by profile and seeded
  data only.
- **Principle 2.** The response models' deliberate absences are airlock
  enforcement expressed as a type — `model_call_payloads` has no field to travel
  in. A refactor that "tidies" schemas by adding a generic passthrough breaks it.
- **Principle 7.** Routes that record telemetry go through `Recorder`. A route
  that writes rows directly is a second writer.

## The loop

```bash
git status --short && openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q          # 302 pass today
npm --prefix apps/web run test && npm --prefix apps/web run typecheck
scripts/check-no-environment.sh && scripts/check-american-english.sh
```

All green before starting. Then propose, clarify, apply, verify, sync, archive.

To exercise every route against real data:

```bash
apps/api/.venv/bin/python -m secondshift_seed --seed 42 --db /tmp/api.db
SECOND_SHIFT_DB=/tmp/api.db SECOND_SHIFT_PROFILE=cloud \
  apps/api/.venv/bin/uvicorn secondshift.api.main:app --port 8099
```

## Verification — characterize before you move anything

A refactor with no characterization test is a rewrite with extra confidence.

- **Capture every current response first.** Hit all six routes against the seeded
  database, save the exact JSON, and assert byte equality after the split. Write
  that test **before** moving a single line.
- **Prove it can fail:** change one field name in a response model and watch the
  characterization test go red. If it stays green it is comparing nothing.
- The static mount is still last: assert that `GET /runs` returns JSON and not
  the PWA's HTML. That is the failure this ordering exists to prevent, and it is
  silent when it happens.
- `POST /entries` still deduplicates a replay and still refuses an id that
  disagrees with its instant.
- The 40+ tests that construct a `Context` directly still pass **unmodified**. If
  you had to change them, you changed the contract.

## Quality bar

The code is the submission. Judges read this repository.

**Never ship:** a `TODO`; a route that changed behavior during a refactor; a
generic passthrough that lets payload text into a response; a second path that
writes rows outside the recorder; a mount order that depends on luck; a docstring
restating the signature.

**Always:** match the surrounding idiom so new code is unidentifiable as new;
preserve the deliberate absences in `schemas.py` and the comments explaining
them; keep writes inside the recorder's lock; let failures be loud. American
English. No hostnames, addresses, usernames or home paths in tracked files.

## Hard stops

Stop, record the question with your recommendation, and move on:

- A `[NEEDS CLARIFICATION]` marker. Do not answer your own.
- A constitution violation. Blocking, not advisory.
- Anything in `NOT_BUILDING.md` — accounts and multi-user are excluded, so an
  auth design that implies users has crossed it.
- Credentials, payment, account settings, or anything outward-facing.
- Rewriting published history or force-pushing.

**Capture is live and taking real ideas.** `POST /entries` is the one route that
must not break. Prove it after every step.

## Report

1. The auth and versioning shapes you proposed, and what each costs when the
   ingest marker resolves either way.
2. The characterization test, and what it caught — **if it caught nothing, say
   so**, and say whether you believe that.
3. What shipped, with test counts, and confirmation that no existing test was
   modified.
4. The five sessions this unblocks, and whether adding a route is now genuinely
   one file.
5. Anything blocked, with your recommendation.
6. What you would do next, and why that rather than the alternative.
