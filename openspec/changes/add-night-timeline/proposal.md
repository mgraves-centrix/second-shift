## Why

Design is one of four equally weighted judging criteria, graded as "a complete,
coherent product experience." The scrubber is the element people screenshot, and
it is the only thing in this project that *shows* the system working rather than
arguing that it does.

It is buildable now because `synthetic-seed` exists — a night of 1,223 events
across 7 lanes over 7.3 hours, reproducible from a seed. That was built
specifically so this did not have to wait weeks for real nights to get dense.

## What Changes

A read-only timeline over one night: drag through it like game film, lanes per
agent role, bars for work with duration and ticks for instants, and hover
surfacing the model call behind an event.

**Rendered with DOM nodes.** Measured against the real night: 0.60ms at p95
against a 16.7ms budget, 28x of headroom. Canvas is seven times faster and it
does not matter — what DOM gives free is `role="slider"`, keyboard scrubbing and
hit testing, and hover is the feature that turns an animation into evidence.
Full numbers in `scripts/spikes/scrubber-render-budget/`.

**API routes that do not exist yet.** There is currently no route serving a
timeline at all. This adds run listing and detail, a windowed timeline, a lane
roster, stages, the invocation tree joined to agent roles, and an event detail.

**Repository gaps this closes.** `invocation_tree()` selects `*` from
`agent_invocations`, which has no `role` column — role lives on `agents`, so the
method literally cannot say which lane an invocation belongs to. `timeline()`
takes no window and returns every row unbounded, and omits `is_synthetic` from
its projection.

Not in this change: the celestial layer, the day view, the trend charts, judge
mode, and anything that writes.

## Capabilities

### New Capabilities
- `night-timeline`: reading one night as a scrubable timeline — windowed
  events, lanes, and the telemetry behind any moment.

### Modified Capabilities
- `telemetry`: the timeline query gains a window and carries the synthetic flag,
  so a seeded night is distinguishable from a real one in the same database.

## Constitution Compliance

| Principle | Status | Note |
|---|---|---|
| 2. Privacy Airlock | **Bounded** | `model_call_payloads` holds raw unredacted content for local-only ideas and must never appear in a hover card. Stated as out of scope so it does not arrive as an obvious follow-up. `tool_calls.query_redacted` is safe by construction. |
| 3. No empty mornings | **Implements** | Every generated night is a run still in flight — five stages complete, one running, no `ended_at_ms`. The view must render that as a correct partial rather than as a spinner or an error. |
| 5. One codebase, two deployments | **Implements** | `is_synthetic` reaches every row but no response, so a judge deployment cannot label itself. This capability adds it to the capability report, because the timeline is the primary judge-facing surface. |
| 6. Scope boundary | **At risk, guarded** | A hover card is one button away from task management. Every affordance here is read-only, and a per-event action needs an explicit override. |
| 7. Telemetry from line one | Compliant | Rendering reads scalar columns only; `payload_json` is fetched for one event on demand, never to draw a frame. |

No violations.

## Decisions taken without a marker

Each of these came out of an adversarial review and was then verified against the
real generated night.

- **Cursor on `(ts_ms, id)`, never `id` alone.** The schema comment claims the
  integer key is monotonic for playback. It is not: depth-first spawning places
  a child's events at earlier timestamps than its siblings, and the real night
  carries **181 inversions in 1,223 rows**.
- **The axis ends at `MAX(ts_ms + COALESCE(duration_ms, 0))`**, not at the last
  event. Bars overhang the final event by **67 minutes** in the real night, and
  an axis computed from timestamps alone clips them.
- **Timezone comes from the entry's stored offset**, joined through
  `runs.entry_id`. `runs` carries only `night_of`, a bare date. Resolving the
  IANA name at read time gives the wrong hour for half the year, which is the
  reason the offset is stored at capture in the first place.
- **Lanes come from a roster route, not from the loaded window.** Two roles get a
  single invocation each for the whole night, so lanes derived from whatever is
  on screen appear and vanish while scrubbing.
- **Bars pack into sub-rows within a lane.** They overlap by construction — the
  generator says so deliberately — and a stage lead's bar spans its entire
  window with its children drawn on top.
- **Events with no invocation are rendered, not dropped.** Stage boundaries carry
  none; the real night has 11 such events, and they are the run's skeleton.
- **Cost is summed from `model_calls` directly**, not from `run_cost`. Every
  rollup view filters `is_synthetic = 0`, so a judge deployment — which is
  entirely synthetic — renders blank from those views. Seeded costs are also
  fabricated rather than drawn from the pricing table, so they are labeled.
- **A bucket keeps the strongest severity, never an average.** One error among
  forty routine events must survive being zoomed out.

## Impact

**New:** `apps/api/secondshift/api/routes/` for the read surface,
`apps/web/app/night/` and its components.

**Changed:** `Repository.timeline` gains a window and the synthetic flag;
`invocation_tree` joins `agents` for role. `CapabilityResponse` gains the
deployment label. Routes must register **before** the static mount in `app.py`,
or they are swallowed by the SPA fallback and return the shell instead of a 404.

**Constraint:** `apps/web` is `output: "export"`, so the night view is a
query-string route with a client-side fetch — `generateStaticParams` cannot
enumerate arbitrary run ids.

**Risk:** `apps/web` is shared with the capture PWA, which is taking real ideas
right now. Breaking it costs captures.

## Open Questions

[NEEDS CLARIFICATION: How does an event reach the model call behind it? `events` carries no `model_call_id`, so the headline feature — hover showing model, tokens and cost — has no supported path. Parsing `payload_json` is forbidden by the telemetry spec and does not carry the fields anyway. Joining on `(agent_invocation_id, ts_ms)` works only by accident: the generator writes both rows at the same instant, and the real night already has 16 timestamps carrying more than one event, so the join is not unique. The options are a migration adding `events.model_call_id` — cheap now, and the first migration against a database holding real captured ideas — or a server-side detail route that does the join and accepts being approximate.]

[NEEDS CLARIFICATION: Where does the night's axis start, and are pre-run capture events shown? Capture events carry `run_id IS NULL`, so `timeline(run_id)` excludes them entirely — the evening's captures are invisible in the run view. Starting the axis at the run's own start is simpler and matches "one night's work". Starting it at the first capture of the evening shows the ideas that caused the night, which is arguably the story, but it means the timeline spans a period during which nothing was running and it needs a second query.]
