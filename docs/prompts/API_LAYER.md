# API layer prompt

**Shipped 21 Sep as `api-layer`. This is a record of what was asked, not a
session to run.** `openspec/changes/archive/2026-09-21-add-api-layer/` is what
happened, and it differs from this file in one way worth knowing.

**Both of the open decisions below were framed around a route that had already
been decided against.** The prompt says authentication "changes the moment
`nebius-executor` adds an inbound ingest route", and rests the versioning
question on that route having an external consumer. That design argued three
transports on 2 Sep and took the one with **no inbound path**: the job writes
telemetry beside its artifacts and the poller collects it. What kept the
questions alive for nineteen days was a single stale line in that proposal's
deliverables list, ninety lines above the section resolving against the route.

Both are now settled in `docs/decisions/0013-the-api-has-no-auth-and-no-version.md`:
no authentication in this layer, scoped to a capability if one ever needs it,
and no `/v1`. Read the sections below for the reasoning that got there, not for
a decision to make.

---

Build out the API layer. Read `openspec/constitution.md`, `CLAUDE.md`,
`docs/ARCHITECTURE.md` and `docs/SPEC_ROADMAP.md` first; they are the rules, not
background.

## Why this one, and why early

`apps/api/secondshift/api/app.py` is **one file** holding every route, the
context factory, the response mappers and the static mount.

**368 lines when this prompt was written, 473 on 19 Sep, 539 on 21 Sep.** A
trend rather than a figure, because the figure ages: the 473 was written into
this file on 19 Sep and was wrong two days later, when `judge-mode` added the
artifact route. That is the argument — not any one number, but that every
session which touches the API leaves this file bigger, and each one had to read
all of it first. `docs/ARCHITECTURE.md`
specifies `api/routes/` in its own directory tree. **It does not exist.**

That is a scheduling problem, not a tidiness one. Five of the sessions in
`00_INDEX.md` need to add routes: `MORNING_INTERVIEW` (decisions and answers),
`ARTIFACTS` (serving files), `NIGHT_PIPELINE` (run on demand), `JUDGE_MODE` (run
the night), and `NEBIUS_EXECUTOR` (telemetry ingest). All five would edit the
same file.

> **Three of those five shipped before this did, and paid the cost.** The
> argument for doing this early was that it makes them parallel; they were run
> in sequence instead, and `app.py` grew by a hundred lines in the process. Only
> `JUDGE_MODE` and `NEBIUS_EXECUTOR` are left to de-collide, so the case for
> this prompt is now the file's size and `ARCHITECTURE.md` describing a tree
> that does not exist — not the scheduling win, which has largely been spent.
> Weigh it against `JUDGE_MODE` on that basis rather than on the paragraph
> above.

## What already exists — do not invent any of it

- **Nine routes, not the six this line used to claim**: `GET /health`,
  `GET /capabilities`, `POST /entries`, `GET /runs`,
  `GET /runs/{run_id}/timeline`, `GET /morning`,
  `POST /decisions/{decision_id}/answer`, `GET /artifacts/{artifact_id}`,
  `GET /events/{event_id}`. The last three arrived with `morning-interview`,
  `morning-screen` and `judge-mode` — each a session that added a route to this
  one file, which is the collision the prompt is about, happening.
- `Context` — a frozen-ish dataclass carrying `repo`, `recorder`, `profile`,
  `report`, `is_synthetic` — built once at startup by `build_context(db_path,
  is_synthetic=, profile=)` and injected with `Depends(get_context)`.
- `create_app(context)` returns the `FastAPI` app. Tests build a `Context`
  directly and wrap it in `TestClient`; that pattern is load-bearing and **74
  test functions across six files rely on it**. A split that changes how a test
  builds an app rewrites all of them, which is how a refactor stops being one.
- `schemas.py`, 301 lines of Pydantic response models, several carrying comments
  explaining what they deliberately **do not** contain — `TimelineEventResponse`
  has no payload field, `EventDetailResponse` has no field prompt or completion
  text could travel in. Those absences are the contract; preserve them.
- **The static mount is last, on purpose**, so every API route matches first:
  `app.mount("/", StaticFiles(directory=WEB_EXPORT, html=True))`. Move it and the
  PWA silently swallows the API.
- `main.py` reads `SECOND_SHIFT_DB` and `SECOND_SHIFT_SYNTHETIC`, and the latter
  is **server-derived, never accepted from a request**. Since `configuration`
  shipped it goes through `config.synthetic_flag()`, which raises on a value it
  does not recognize rather than resolving to false — do not reintroduce a
  permissive parse. `python -m secondshift.config show` prints what both
  resolved to and where from.
- Three migrations: `0001_initial.sql`, `0002_capture.sql` and
  `0003_eval_synthetic.sql`.

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
python3 scripts/gate.py
```

**One command, and it is the one CI runs.** Ten gates in order — airlock, the
two repository guards, specs, the orchestrator suite, web unit/types/build, a
browser test, and a mutation check — stopping at the first failure with that
gate's exit code. About 85 seconds. `docs/development/GATES.md` has the table.

The hand-run list this prompt used to carry here was six commands typed in a
remembered order, and `TEST_HARNESS.md` shipped on 17 Sep specifically to
replace it. If you find yourself running the pieces separately, run the gate
instead: it is the only definition of passing this project has.

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
