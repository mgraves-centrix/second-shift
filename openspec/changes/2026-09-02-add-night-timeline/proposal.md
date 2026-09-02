## Scale

**L2 — Feature.** One capability with one contract: a read API over a recorded
night, and the component that renders it. It spans `apps/api` and `apps/web`, but
adds no architectural decision — the rendering question that would have needed
one was measured in Spike D, and the data contract it reads was designed for this
on day 1. Proposal, spec delta and tasks; no design doc.

## Why

Design is one of four equally weighted judging criteria, graded as a complete
product experience rather than a technical proof. Everything else in this project
*argues* that the system works. This is the thing that shows it working, and it is
the element people screenshot.

It is also built once and used three times — the night view, judge mode's "run the
night", and the shared time axis the trend charts brush against later. It is
designed as one component with three callers.

Nothing renders a night today. `Repository.timeline()` and
`invocation_tree()` exist and are tested, and no route exposes them: the API is
capture-only. A thousand rows of evidence per night are written and unreadable.

## What Changes

**Three read routes**, and the split between them is the contract rather than a
convenience.

`GET /runs` lists recorded nights. `GET /runs/{id}/timeline` returns the whole
night in one response — the scalar event columns, the lanes those events
recorded, the invocation tree, and the run's frame. `GET /events/{id}` returns
one event's `payload_json` and the model call joined through its invocation.

**The timeline route cannot return `payload_json`.** The scalar-columns property
is currently a docstring on `Repository.timeline` and a promise the renderer
keeps. Making it two routes makes it structural: a renderer cannot parse JSON to
draw a frame, because the frame data does not contain any.

**The whole night in one request, deliberately.** 1,223 events is roughly 180KB
before compression. A windowed query would mean a fetch mid-drag, and "no loading
state mid-drag" is the requirement. The window is a rendering concern, not a
query one.

**A DOM scrubber, rendered incrementally.** Spike D measured it: 0.1ms p50 and
0.3ms max per steady frame against a 16.7ms budget, and — the finding that
decided it — a steady cost that is *flat* in night size where canvas's is linear.
Canvas is the approach that degrades as nights get denser. DOM also brings hit
testing, focus, keyboard interaction and screen-reader semantics that canvas
would have to reimplement, all of which this capability requires.

**Bars and ticks distinguished by shape, not only width.** The same spike found
that at full-night zoom on 1,200px one pixel is 22 seconds, so the median bar is
1.4px — indistinguishable from a tick. `duration_ms` non-null versus null is the
difference between a forty-second crawl and an instantaneous write, and it has to
be visible at a glance. Bars get a minimum width and ticks a different shape.

**Keyboard scrubbing, and the moment announced.** Arrow keys move the playhead;
the current moment is announced politely. A timeline that answers only to a mouse
excludes people and reads as unfinished.

**Synthetic nights are shown and labeled.** They are the only nights that exist
yet, so the view must render them — and a screenshot of one must never be
mistaken for evidence. Every run carries `is_synthetic` to the client and a
synthetic night says so on its face, the same way the judge instance must.

Not in this change: the celestial layer, the day view, the trend charts, judge
mode, and zoom. Nothing here writes.

## Capabilities

### New Capabilities
- `night-timeline`: the playback contract behind the scrubber — reading a
  recorded night, and rendering it as time.

## Constitution Compliance

| Principle | Status | Note |
|---|---|---|
| 1. Brain plaintext under git | Not applicable | Reads telemetry, never memory. |
| 2. Privacy Airlock | Compliant | Read-only, same-origin, no egress. The view renders what a run recorded and adds no path by which anything leaves; `payload_json` is served to the same local surface that already reads entries. |
| 3. No empty mornings | **Implements** | "Honest at rest" is this principle rendered. A night with a failed stage must look like one — a degraded run that renders as a smooth success is the visual form of hiding partial results, and it is the same failure the principle forbids in the morning view. |
| 4. Text-first | Compliant | No voice surface. The timeline is readable and operable by keyboard, and announces the moment for a screen reader. |
| 5. One codebase, two deployments | **Implements** | One component, three callers — the night view, judge mode, and the trend axis. No demo branch: judge mode is a different caller of the same component, and a synthetic night is labeled rather than rendered differently. |
| 6. Scope boundary | Compliant | It reads. A timeline that grew an edit or retry control would have crossed into task management, and the absence of any write path is what keeps it out. |
| 7. Telemetry from line one | **Depends on** | This is the first thing to read what telemetry has been writing since day 1. It adds no agent invocation and no model call, so it opens no telemetry row of its own. `is_synthetic` reaches the client so a seeded night is never presented as measurement. |

No violations.

## Decisions taken without a marker

- **`events.lane` is the lane, and nothing is joined to compute it.** The obvious
  reading — lane is the role of the invocation that produced the event — is wrong
  in three ways against the real data. `agent_invocations` carries no role at all
  (it is on `agents`, through `agent_id`); 11 of 1,223 events have no invocation
  (stage boundaries); and 20 events record `system` while their producer's role is
  `builder` or `critic`. The column is pre-denormalized for rendering and is a
  decision made at write time, which is exactly why it exists. Seven lanes are
  legible at a glance and 182 invocations are not, so depth renders as nesting
  within a lane rather than as more lanes.
- **The whole night is fetched once.** See above: a windowed query trades a
  requirement for an optimization that the measurement says is unnecessary.
- **Full-night zoom, no zooming in this change.** The scrubber's claim is that
  dragging through six hours feels like video. Zoom is a second interaction
  model, and the bar-versus-tick legibility problem it would solve is solved
  more simply by shape.
- **A synthetic night is rendered, not filtered.** Rollups exclude synthetic rows
  because they are measurements. A viewer is not a measurement; hiding the only
  nights that exist would leave the view empty and untestable.
- **No `payload_json` on the timeline route.** Structural rather than
  documented, because "the renderer must never parse JSON to draw a frame" is a
  property, and a property enforced by what the API cannot return does not
  depend on the renderer remembering it.

## Impact

**New:** three read routes on the API and their schemas; a night route and
scrubber component in `apps/web`.

**Changed:** `Repository` gains a run listing and the two joined reads the detail
route needs. Nothing existing changes behavior — the capture path is untouched,
and it is taking real ideas.

**Risk:** the measurement was taken in headless Chromium on server hardware and
covers script, style and layout — not paint, and not a phone. The check on that
is looking at it, which is part of this change's verification rather than a
follow-up.
