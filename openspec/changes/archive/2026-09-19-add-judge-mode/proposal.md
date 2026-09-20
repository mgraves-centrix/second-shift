# Add `judge-mode` — the product, demonstrable in one sitting

## Scale classification

**L4 — Initiative.** It is the last unshipped capability on the roadmap, it is
what a judge actually sees, and grounding it turned up four defects in shipped
code that the demo makes visible. Design doc included. This will not land in one
sitting and the task groups are ordered so each leaves the tree green.

## Why

A judge has minutes and no context. They will not read this repository, install
anything, or wait for a night to run.

So the test is what they meet. I stood up the judge deployment as it exists
today — `cloud` profile, `is_synthetic=1`, a seeded night, the built export
served by the API — and opened all three surfaces.

**A judge lands on a textarea that says "What's the idea?"** That is the capture
screen, designed for a person at 3am who already knows what this is. Nothing on
it says the product works overnight, produces artifacts, or interviews you. The
prompt's first quality bar is "a judge lands on a URL and, within one screen,
knows what the product is." Today that fails outright.

**The interview is empty.** `secondshift_seed` writes no `decisions`, so
`/morning` renders "Nothing is waiting on you." The roadmap calls the interview
"the product". A judge opening it finds nothing to do.

**Nothing can be opened.** The seeder's own docstring says its artifacts "have
no bytes behind them", and no route serves artifact files. "Idea in, artifact
out" is described, never demonstrated.

The night view, by contrast, needs nothing. 1223 events across 7 lanes, a
`SYNTHETIC` badge and `5 OF 6 STAGES · DISTILL RUNNING` on its face.

## The open decision — replay or a live run — is settled by evidence

The prompt says to time both. **There was nothing to time**, and the reason is
better than a stopwatch:

1. **A live night is refused on `cloud`.** `night/__main__.py` exits
   `EXIT_NO_REASONER`, and its comment says why it was added: "A night run
   against it closed every stage `complete` with the prompt echoed back as the
   artifact and moved each idea to `answered`."
2. **Forcing it would reintroduce that defect.** `Registry.bind("cloud")` binds
   `EchoReasoner`, which returns its last message verbatim — the idea text, five
   times, as five artifacts.
3. **Even then it would render an empty timeline**, for the reason below.

Replay, and the seeded night is the replay. It takes **0.78s** to write.

## The finding that outgrew this capability

**A real night writes zero `events` rows.** Measured, not inferred:

| | events | lanes | invocations | model calls |
|---|---|---|---|---|
| a real six-stage night through `run_entry` | **0** | **0** | 6 | 6 |
| `secondshift_seed --seed 42` | 1223 | 7 | 182 | 362 |

`record_event` is defined on the recorder and called from nowhere in `night/`.
`record_model_call` and `record_tool_call` do not write events either. So the
scrubber — the signature UI element — **has never rendered a real night and
structurally cannot.** The two real nights that ran on the Spark on 16 Sep are
invisible in the night view.

**This is not a spec violation, and that is the interesting part.** The telemetry
spec requires events be *renderable without parsing*; nothing ever required the
night to emit them. The browser gate passes because it drives seeded data. A
capability can be correct against every requirement written down and still not
do the thing the product is for.

It gives `judge-mode` nothing — the demo replays seeded data that already has
events — and it is included because the alternative is a personal instance whose
best screen is permanently blank.

## What Changes

Seven groups, each leaving the tree green:

1. **The judge requirement moves out of `nebius-executor`.** That parked change's
   delta already claims "The judge instance is this code, with no real data".
   Two changes asserting one requirement means whichever archives second
   duplicates or overwrites the other.
2. **A night emits events**, so the night view works on the personal instance.
3. **Artifacts are served and have bytes**, so "artifact out" is reachable.
4. **The seed writes decisions**, so the interview has an agenda.
5. **A landing page that says what the product is** within one screen.
6. **A container image** for ADR 0009's no-GPU Serverless AI Endpoint.
7. **The synthetic-containment gaps** below.

## Synthetic containment — three gaps, one of them a live documentation bug

- **The eval tables carry no `is_synthetic` column at all**, and the runner never
  filters on one. An eval run on a judge instance writes unmarked rows into the
  measurement spine — the contamination principle 5 exists to prevent.
- **`model_call_payloads` says "must never be synced, uploaded, or included in a
  judge deployment" — as a SQL comment, with nothing enforcing it.** The API
  correctly never joins it; nothing stops a deploy shipping the file.
- **The README's demo recipe omits `SECOND_SHIFT_SYNTHETIC=1`.** Anything
  captured against an instance stood up that way is written `is_synthetic = 0`.

## Corrected while grounding

An earlier reading of this held that `Registry.bind("cloud")` would fail on a
no-GPU VM because retrieval is local on every profile. **It does not.**
`_local_embedder` raises only when `embedder_model` is *unset*; `VllmEmbedder`
does not probe on construction, so binding succeeds against an unreachable
endpoint and `_retrieve` already treats retrieval as attempted-never-required.
The real obligation is narrower and belongs in group 6: the container must ship
`config/models.toml`, or the judge instance refuses to bind for a reason that
has nothing to do with the demo.

## What does not ship

- **No `if DEMO_MODE`.** Principle 5. If this needs one line of business logic
  that exists only for the demo, the fix is upstream.
- **No live night on the judge instance.** Above.
- **No real data, ever.** Every row synthetic, and group 7 is what makes that
  hold rather than hoping.

## Impact

- New spec `judge-mode`; deltas to `telemetry`, `artifacts`, `synthetic-seed`,
  and `nebius-executor` (which loses the judge requirement).
- `apps/api/secondshift/night/`, `telemetry/recorder.py`, `api/app.py`,
  `packages/seed/`, `apps/web/app/`, and a new `deploy/judge/`.
- The capture PWA's behavior is unchanged. It is taking real ideas.
