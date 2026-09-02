# Judge mode prompt

Paste as the first message of a fresh session.

**Depends on `NIGHT_PIPELINE.md`, `ARTIFACTS.md` and `MORNING_INTERVIEW.md`, and
on the judge deployment target being decided.**

---

Build `judge-mode`. Read `openspec/constitution.md`, `CLAUDE.md`,
`docs/decisions/0004-nebius-workload-split.md` and `docs/SPEC_ROADMAP.md` first;
they are the rules, not background.

## Why this one

A judge has minutes and no context. They will not read the repository, install
anything, or wait for a night to run. Judge mode is the entire product,
demonstrable in one sitting, with none of the subject's real data in it.

It is also **principle 5 made concrete**: the personal instance and the judge
instance are the same code separated only by compute profile. Never a fork, never
a branch, never an `if DEMO_MODE` in business logic. If this capability needs one
line of business logic that exists only for the demo, the principle has been
broken and the fix is upstream, not here.

## What already exists — do not invent any of it

- `SECOND_SHIFT_SYNTHETIC` is read by `api/main.py` and is **server-derived,
  never accepted from a request** — the capture schema deliberately has no
  `is_synthetic` field, because accepting it would let a real entry be excluded
  from every measurement, unrecoverably. Since `configuration` shipped it parses
  strictly: `1`, `true`, `yes`, `on` and their negatives, and **anything else
  raises rather than resolving to false**. That matters most here — a typo in the
  judge deployment's environment used to mean its seeded persona wrote rows
  indistinguishable from real ones. Confirm with
  `python -m secondshift.config show`, which prints what it resolved to.
- Every accumulating table carries `is_synthetic`, and the rollup views already
  exclude it.
- `python -m secondshift_seed --seed 42` writes a full night: 1,223 events over
  7.32 hours across 7 lanes, 182 invocations at depth 3, 362 model calls with
  costs, 6 failures. Deterministic by seed, so **a screenshot is reproducible**.
- The scrubber renders that night today and labels a synthetic run as synthetic
  on its face.
- `resolve_profile` degrades to `cloud` when there is no local stack, and reports
  `local-only` unavailable **with the specific finding that caused it** — which
  is the honest behavior to demonstrate, not a wart to hide.

## The open decision

**The deployment target, which is not yours to pick.** It is a
`[NEEDS CLARIFICATION]` marker in the `nebius-executor` change and it closes an
open risk in ADR 0004. If it is unresolved, stop and say so.

**What is yours:** whether "run the night" in judge mode replays a recorded night
or executes a real one. Replay is reliable and reproducible; a live run is
evidence. **Do not decide by preference** — time both against the real pipeline
and report the numbers. If a live run takes four minutes, no judge will watch it,
and the answer is replay with a live run available on request.

## What good looks like

- A judge lands on a URL and, within one screen, knows what the product is.
- **It says it is a demo, in the UI, without being asked.** The constitution
  requires it.
- Zero real data. Not scrubbed real data — generated data, every row
  `is_synthetic = 1`.
- "Run the night" produces something to watch on the scrubber within a span a
  person will actually sit through.
- The two-ideas comparison is readable: a `local-only` artifact at $0.00 cloud
  spend beside a `cloud-assisted` one that fanned out to Nebius jobs, both
  numbers read from `model_calls` rather than asserted.
- The airlock is *demonstrated*, not described: `local-only` shown unavailable on
  the cloud profile, with its reason.
- It survives being opened by ten people at once and by nobody for three days.

## Scope — what NOT to build

- **No fork, no branch, no `if DEMO_MODE`.** Compute profile and seeded data.
- **No real data, ever**, including yours as a sample.
- **No auth.** Single-tenant by design; `NOT_BUILDING.md` excludes accounts.
- **No new UI components.** Judge mode is a caller of what exists. If it needs a
  new component, that component belongs to whichever capability owns it.
- **No write path from the public internet** beyond what the demo needs.

## Constitution hooks

- **Principle 5 governs, and this capability is its test.** Same code, different
  profile, labeled in-UI, zero real data, `is_synthetic = 1` throughout.
- **Principle 2.** The demo runs the real airlock. Showing `local-only`
  unavailable on a cloud profile is the feature.
- **Principle 7.** Synthetic rows never enter a measurement. Assert it here too,
  because this is the instance most likely to pollute one.

## The loop

```bash
git status --short && openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q          # 302 pass today
npm --prefix apps/web run test && npm --prefix apps/web run typecheck
scripts/check-no-environment.sh && scripts/check-american-english.sh
```

All green before starting. To stand one up locally against a real seeded night:

```bash
apps/api/.venv/bin/python -m secondshift_seed --seed 42 --db /tmp/judge.db
SECOND_SHIFT_DB=/tmp/judge.db SECOND_SHIFT_PROFILE=cloud SECOND_SHIFT_SYNTHETIC=1 \
  apps/api/.venv/bin/uvicorn secondshift.api.main:app --port 8099
```

Then propose, clarify, apply, verify, sync, archive.

## Verification

- **Grep the deployed database for the subject's real entries and find nothing.**
  Not a review — a test.
- Every row in every accumulating table has `is_synthetic = 1`.
- The demo label is present on every surface, asserted, not eyeballed.
- The rollup views on the judge instance exclude everything, because everything
  is synthetic — and that is the correct, provable outcome.
- A source scan finds no `DEMO_MODE`-style branch in business logic. **Prove the
  scan can fail:** add one temporarily and watch it go red, then remove it.
- **Prove the real-data test can fail:** insert one non-synthetic row and watch
  the assertion catch it. A privacy check that has never caught anything is a
  hypothesis.
- Open it in a browser, screenshot every surface, **and read the screenshots.**
  Then have someone who has not seen it try to say what the product is.

## Quality bar

The code is the submission. Judges read this repository.

**Never ship:** an `if DEMO_MODE` in business logic; real data; a screenshot that
is not reproducible from a seed; a demo that needs a person standing next to it;
lorem text; a `TODO`.

**Always:** same code, different profile; keep tables append-only; let failures
be loud. American English. No hostnames, addresses, usernames or home paths in
tracked files.

## Hard stops

- A `[NEEDS CLARIFICATION]` marker — including the deployment target, which is
  not yours to answer.
- A constitution violation. Blocking, not advisory.
- Anything in `NOT_BUILDING.md`.
- Credentials, payment, account settings, or anything outward-facing.
- Rewriting published history or force-pushing.

## Report

1. The replay-versus-live timing, and what you chose.
2. Screenshots of every surface, and what a stranger said the product was.
3. The proof that no real data is present.
4. What shipped, with test counts.
5. Anything blocked, with your recommendation.
6. What you would do next, and why that rather than the alternative.
