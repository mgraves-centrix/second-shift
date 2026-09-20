# Design — `judge-mode`

## The night that writes nothing

`record_event` is defined on the recorder and called from nowhere in `night/`.
Not by `run_entry`, not by `_run_stage`, not by `record_model_call` or
`record_tool_call`. A six-stage night therefore produces six invocations, six
model calls, and **no timeline at all**.

The fix is not "add logging". The question is *which* events, and the answer
comes from what the scrubber draws: lanes, bars and ticks. So the night records
exactly what has a lane and a span —

| when | lane | kind | span |
|---|---|---|---|
| a stage starts / ends | `system` | `stage_start` / `stage_end` | the stage |
| an invocation starts / ends | the agent's role | `invocation` | the turn |
| a stage fails | the agent's role | `failure`, severity set | an instant |
| a stage is skipped | `system` | `note` | an instant |

**The lane is the lane the work belonged to, never the role of whatever produced
the row.** `night-timeline`'s spec already says so, and a stage boundary has no
producer at all — which is why it is `system` rather than borrowed from the
stage's agent.

Events are written inside the stage transaction that already exists, so a
crashed night keeps the events for the stages that committed. That is principle
3 applied to the record as well as to the output: a night that stopped part-way
should be *visible* as having stopped part-way.

This buys `judge-mode` nothing. It is here because the alternative is shipping a
personal instance whose best screen is blank for every real night, and because
the demo would otherwise be the only place the product looks like it works.

## Why the seeded night stays the demo

Three independent reasons, any one of which is sufficient:

1. `night/__main__.py` refuses to start on `cloud` — `EXIT_NO_REASONER`.
2. `Registry.bind("cloud")` binds `EchoReasoner`, which returns its last message
   verbatim. Every stage would write the idea text as its artifact. That is the
   defect the refusal in (1) was added to prevent.
3. A judge will not wait. The one recorded real night is **192 seconds for five
   stages**; the seed writes a complete night in **0.78s**.

So "run the night" is not a button that runs a night. The demo *is* a recorded
night, and the honest framing is to say so rather than to animate a fake one.

## The first screen

Capture is the wrong landing for a stranger and the right one for the subject.
Both are true, and `frontend` already established the shape of the answer: one
token system, and what a surface shows is decided by the **served capability
report**, never a build flag.

So the explanation is a block that renders on the capture surface when the
report resolves `cloud` — the same signal that already drives the demo label,
via the same fetch. No second build, no `DEMO_MODE`, no new endpoint. On the
personal instance it is absent and capture is untouched, which matters because
`frontend` measured what chrome above the input costs the privacy choice at a
keyboard-up viewport: `local-only` goes from 79% visible to 0%.

**It therefore renders below the capture control, not above it.** A judge
scrolls one screen; the person capturing at 3am never sees it. That asymmetry is
already the rule this project established and is not being re-litigated here.

## Artifacts, and the smallest route that is honest

`artifacts` shipped files on disk and no way to read them. The route is
deliberately narrow:

- addressed by artifact **id**, not by path, so the URL cannot express a path at
  all and traversal is not a check that can be forgotten;
- the row is looked up, the path resolved under the artifact root, and a file
  that is not there is a **404 rather than an empty 200** — an artifact row
  naming a missing file is a defect, and answering it with emptiness hides one;
- content type from the recorded kind, never sniffed.

`model_call_payloads` is not reachable from it, and the response has no field it
could travel in — the same structural argument `/events/{id}` already makes.

## Synthetic containment is enforced, not documented

Three holes, and the shape of each fix:

- **Eval tables have no `is_synthetic`.** A migration adds it, and the runner
  sets it from the deployment the same way capture does — server-derived, never
  from a request. The views that read results exclude it.
- **`model_call_payloads` must never reach a judge deployment**, and today that
  is a SQL comment. It becomes a check in the deployment package's build that
  can fail, and a test that proves it fails.
- **The README recipe omits `SECOND_SHIFT_SYNTHETIC=1`.** Fixed, and the strict
  parser means a typo raises rather than silently meaning "real".

The through-line: every one of these was a sentence somebody wrote hoping a
later reader would obey it. Principle 5's violation clause names "synthetic rows
without `is_synthetic = 1`" — this is the inverse and worse, real-looking rows
on the instance that is supposed to have none.

## The container

ADR 0009 settles where: a no-GPU Serverless AI Endpoint, ~$36/month for
`2vcpu-8gb`. What it must carry is decided by what binding needs:

- `config/models.toml`, because `_local_embedder` refuses to bind when
  `embedder_model` is unset — and refuses *loudly*, which on a demo reads as a
  broken deployment rather than as the correct refusal it is;
- the seeded database, built at image time so the demo is identical on every
  cold start and the seed is a build step rather than a runtime dependency;
- the built web export, served by the API on one origin — no CORS, no second
  process;
- `SECOND_SHIFT_SYNTHETIC=1`, `SECOND_SHIFT_PROFILE=cloud`.

It must **not** carry the brain, a real database, or `model_call_payloads`.
