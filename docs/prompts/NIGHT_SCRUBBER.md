# Night scrubber prompt

Paste as the first message of a fresh session. Entirely local — no Spark, no
tailnet, no credentials.

---

Build the night scrubber. Read `openspec/constitution.md`, `CLAUDE.md`, and
`docs/SPEC_ROADMAP.md` first; they are the rules, not background.

## Why this one

Design is one of four equally weighted judging criteria, and it is graded as "a
complete, coherent product experience, not just a technical proof of concept."
The scrubber is the element people screenshot. Everything else in this project
argues that the system works; this is the thing that *shows* it working.

It is also built once and used three times — the night view, judge mode's "run
the night", and the shared time axis the trend charts brush against. Design it
as one component with three callers, not as a night view you later generalize.

## What already exists — do not invent any of it

A generated night is real data, verified on this machine:

```
1,223 events over 7.3 hours across 7 lanes
  critic 523, distiller 241, researcher 211, builder 202, system 31, ...
1,019 events carry duration_ms (render as bars) / 204 do not (ticks)
182 invocations, tree depth 3
```

Generate one and point the API at it:

```bash
apps/api/.venv/bin/python -m secondshift_seed --seed 42 --db /tmp/night.db
SECOND_SHIFT_DB=/tmp/night.db SECOND_SHIFT_PROFILE=cloud \
  apps/api/.venv/bin/uvicorn secondshift.api.main:app --port 8080
npm --prefix apps/web run dev
```

The data contract is already shaped for this and is not yours to change:

- `Repository.timeline(run_id)` returns scalar columns only — `ts_ms`, `lane`,
  `kind`, `label`, `severity`, `duration_ms`, `agent_invocation_id`. **The
  renderer must never parse JSON to draw a frame.** `payload_json` is fetched on
  hover, for one event.
- `duration_ms` non-null is a bar; null is a tick. That distinction is the
  difference between a forty-second crawl and an instantaneous write, and it
  must be visible at a glance.
- `Repository.invocation_tree(run_id)` gives parentage and depth — the lanes.
- `model_calls` join to invocations, so hovering an event can surface the model,
  the tokens and the cost behind it.

If you need an API route that does not exist, add it — but read
`openspec/specs/telemetry/spec.md` first and keep the scalar-columns property.

## The open decision

**DOM nodes or canvas?** `docs/WEEK_ONE.md` already records the abort criterion:
if 60fps is not reachable with DOM, move to canvas. Starting with canvas skips a
likely rewrite; starting with DOM gets accessibility, inspectability and hit
testing for free, and at ~1,200 events may simply be fast enough.

**Do not decide this by preference.** Measure it: render the real generated night
both ways at 20x and report frame times. Then propose, with the numbers.

## What good looks like

Concretely, not "make it nice":

- **It reads as game film.** Dragging through six hours feels like scrubbing
  video — continuous, responsive, no snapping to buckets, no loading state
  mid-drag.
- **Density is legible.** A quiet 3am and a frantic research burst look
  different at a glance, without reading a single label.
- **Lanes mean something.** A viewer should be able to tell, without a legend,
  that several agents were working at once and which one was leading.
- **Hover earns its place.** It surfaces the model call behind an event — model,
  tokens, cost. That is what turns an animation into evidence of a real system.
- **It is honest at rest.** A night with a failed stage looks like a night with a
  failed stage. Do not render a smooth success over a degraded run.
- **Keyboard scrubbing works.** Arrow keys move the playhead, and the current
  moment is announced. A timeline that only responds to a mouse excludes people
  and reads as unfinished.

Give it real design intent. Default component-library styling is a scored loss.

## Scope — what NOT to build

- **The celestial layer.** Week 6, after this works. Do not preclude it: the
  playhead must expose the current timestamp and the entry's timezone, which is
  all the sun and moon positions will need.
- **The day view.** Different problem — sparse days, snapping, a snapshot grid.
- **The trend charts.** They share this time axis later; do not build them.
- **Judge mode.** Same component, different caller, later.
- **Anything that writes.** This reads. It must not mutate a row.

`NOT_BUILDING.md` still applies. A timeline that grows an edit control has
crossed a line and needs an explicit override.

## The loop

```bash
git status --short && openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q
npm --prefix apps/web run test && npm --prefix apps/web run typecheck
scripts/check-no-environment.sh && scripts/check-american-english.sh
```

All green before starting. Then:

```bash
git checkout -b feature/night-timeline
openspec new change add-night-timeline
```

Write the proposal, the spec delta, and tasks. Run an adversarial pre-review
agent against the spec before you write it — that has found real defects three
times now, including four in shipped code before `capture`. Then:

```bash
openspec validate add-night-timeline --strict
```

**Stop for any clarification marker.** Do not answer your own. Commit the
proposal, record the question with your recommendation, and wait.

## Verification — a green suite is not enough here

A test suite cannot tell you whether a scrubber feels right. It can tell you
whether it is correct. Do both.

**Automated**, and these must be able to fail:
- Scrubbing to a timestamp shows the events at that timestamp and not others.
- 1,200+ events render without the component reading `payload_json`.
- Lanes map to invocation roles, and nesting depth is represented.
- Hover on an event surfaces the model call joined to it.
- Keyboard scrubbing moves the playhead and announces the moment.
- Frame time at 20x, asserted against a budget rather than eyeballed.

**Visual.** Actually look at it. Use the browser tools: navigate to the dev
server, take screenshots at several points in the night, and read them. If it
looks like a progress bar with dots on it, it is not done. Report what you saw,
not what you built.

Then the usual gates: full suite, both check scripts, strict validation, sync
deltas into canonical specs, **verify requirement by requirement and gate on the
result** — a failed verification once silently dropped a requirement — then
archive, merge with `--no-ff`, push.

## Quality bar

**Never ship:** hardcoded sample data or a fixture array standing in for the API;
lorem text; a component that re-renders the whole timeline on every pointer move;
a test that passes with the implementation deleted; `any` in TypeScript; a
`useEffect` that fetches without cleanup; magic numbers for layout that should be
tokens; a docstring restating the signature.

**Always:** read from the real API; match the existing `apps/web` idiom — read
`app/page.tsx` and `app/globals.css` first; keep the capture PWA working, it
takes real ideas and `apps/web` is shared; American English; no hostnames, paths
or usernames in tracked files.

## Agents

Read-only agents in parallel, freely: an adversarial spec review, a survey of
the existing web app's conventions, a critique of your rendering approach before
you commit to it.

If you delegate implementation, give disjoint file ownership explicitly and say
so in the agent's prompt. Do not have two agents in `apps/web/app` at once.

## Report

1. **The DOM-versus-canvas measurement**, with numbers, and which you chose.
2. What shipped, with test counts.
3. What you saw when you looked at it — honestly. If it is not good yet, say so.
4. Anything blocked, with your recommendation.
5. What you would do next, and why that rather than the alternative.
