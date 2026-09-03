# Morning interview prompt

Paste as the first message of a fresh session. Local to build; a real phone to
judge it.

**Depends on `FRONTEND.md`. Runs in parallel with `NIGHT_PIPELINE.md` and
`TEST_HARNESS.md`; must not be in `apps/web/app/` at the same time as
`FRONTEND.md`.**

> **`FRONTEND.md` had not shipped when this ran, and that split the capability.**
> Its own prompt says it "must land before `MORNING_INTERVIEW.md`", and the
> reason was concrete: `/` and `/night/` had no navigation between them, and
> design tokens were drifting across `app/globals.css` and
> `components/scrubber/scrubber.module.css`. **`frontend` shipped on 3 Sep and
> closed both**, so `app/morning/` is unblocked: add the route to
> `SURFACES` in `components/shell/Shell.tsx` and it appears in the nav and the
> capture footer at once.
>
> So **the server half shipped and the screen did not** — briefing assembly,
> the interviewer raising decisions, answering with a modality, and the policy
> upgrade, reachable at `GET /morning` and `POST /decisions/{id}/answer` and
> exercised by tests rather than through a rendered page. (Those routes were
> missing when this first shipped and a later audit added them — the package had
> no caller at all.) The screen is `FRONTEND.md`'s to unblock, and the report
> item asking whether the interview *felt* like an interview is unanswerable
> until it exists.

---

Build `morning-interview`. Read `openspec/constitution.md`, `CLAUDE.md`,
`docs/decisions/0005-interview-stays-in-the-morning.md` and
`docs/SPEC_ROADMAP.md` first; they are the rules, not background.

## Why this one

**The interview is the product.** Everything else is scaffolding for this
screen. The pitch is "it interviews you in the morning about what it got stuck
on," and a submission without it is a well-instrumented batch job.

It is also the only place the eight-week claim becomes visible to a person. The
brain gets better because the interview corrects it; nothing else writes belief.

## What already exists — do not invent any of it

- **The interviewer agent is what raises a decision**, not the night. The
  schema says so — `raised_by_invocation_id` is commented *which interviewer
  version asked* — and the shipped `interviewer.v1.md` prompt agrees: "The night
  has run; some of it worked and some of it got stuck. Your job is to ask the
  person the smallest number of questions that would have unblocked the most
  work." So the questions are produced at briefing time by reading the night's
  record, and `night-pipeline` correctly does not write this table.
- `decisions`: `question`, `rationale` (*why the agent could not proceed*),
  `blocking_stage`, `raised_by_invocation_id` (*which interviewer version asked*),
  `answer`, `answer_modality` CHECK over `voice` and `text`, `status` CHECK over
  `open`, `decided`, `deferred`, `queued-for-tonight`, `obsolete`, and
  `consumed_by_run_id`. **The whole interview state machine is already in the
  schema and nothing wrote it until this capability did.**
- `resolve_policy(..., upgrade_decision_id=)` widens `local-only` to
  `cloud-assisted` **only** with an attributable decision, recording
  `policy_source = 'decision-upgrade'`. That is the mechanism for "may I take
  this one to the cloud?" — it exists; use it rather than inventing a flag.
- ADR 0005 settled that the interview is **morning only**. Capture stays instant;
  friction at capture is the one thing that would kill dogfooding. Do not add an
  evening or at-capture variant.
- `BrainRepo` reads and commits the brain. Sync stages `journal/` rather than the
  tree, so a hand-edited topic file is never swept into an automated commit.
- The scrubber exists and is the shared time axis for anything you render.

**Speech, and its exact state:**

- **Your speech is buildable now.** `getUserMedia` plus an `AnalyserNode` gives
  real-time frequency and amplitude with no unproven dependency. Spike A
  confirmed `getUserMedia` passes on the phone over the Tailscale Serve TLS
  origin.
- **Its speech is no longer blocked.** MagpieTTS was verified on the Spark
  2026-08-28 — five fixed voices, RTF ~0.44, 22.05 kHz, 1.85 GiB alongside the
  reasoner. The same `AnalyserNode` reads it through `createMediaElementSource`.
  One component, two sources.
- **There is no ASR.** The Parakeet Realtime EOU end-of-utterance detector — the
  80–160ms decision that makes push-to-talk feel right — is bound in ADR 0006 and
  **has never been run.** Spike C left a working NeMo 3.1.0 aarch64 environment
  for it to inherit.

## The open decision

**What the briefing is a delta of.**

"Briefing from the log delta" is in the roadmap and it is underspecified. The
delta since when — the last interview, the last night, the last time you opened
it? Each gives a different briefing on a morning after a night you skipped.

**Do not decide this by preference.** Decide it by writing out what the briefing
says on three concrete mornings: after a clean night, after a night you never
read, and after two nights with no interview between them. One rule will read
wrong on at least one of them; the right answer is the rule where none of the
three is confusing. Put the three briefings in the proposal.

The second open thing: **ASR is not built and this capability must not wait for
it.** Principle 4 is explicit — TTS and ASR must not be on the critical path, and
voice upgrades a working text path rather than gating one. Decide and state
whether you are building the input visualization against a microphone with no
transcription behind it, or deferring the input half entirely. Either is
defensible; silently half-building it is not.

## What good looks like

- **Every turn is completable by typing.** Not as a fallback that feels like
  one — as the primary path that voice decorates. Unplug the microphone and the
  interview is unchanged.
- The briefing is short enough to read standing up, and says what happened, what
  it produced, and what it could not decide.
- A question carries its **rationale** — why the agent could not proceed — because
  a question without one is a quiz.
- Answering writes the decision, and the decision is visibly consumed: a
  `queued-for-tonight` answer shows up as tonight's input.
- Deferring is a first-class outcome. So is "this is obsolete now."
- An answer that widens policy does so through `upgrade_decision_id`, and the
  screen says plainly that the idea is about to leave the machine.
- If you build the speech visualization, it shows the **turn-taking machinery** —
  who holds the turn, whether the system is listening or thinking, and the gap
  between speech ending and a response starting. A bouncing waveform is
  decoration and every demo has one.

## Scope — what NOT to build

- **No general chat interface.** `NOT_BUILDING.md` excludes it by name: the
  interview is structured and agenda-driven, and an open chat box would quietly
  replace it and make the product a worse ChatGPT. This is the single most
  likely way this capability goes wrong.
- **No ASR spike.** If you need it, that is its own session.
- **No evening or at-capture interview.** ADR 0005.
- **No task list.** Answered, deferred and obsolete are decision states, not a
  backlog.
- **No editing artifacts in-app.** They land as files.

## Constitution hooks

- **Principle 4 governs.** Every voice interaction has a working text equivalent
  that is not a degraded fallback. A turn that can only be completed by speaking
  is a violation, not a limitation.
- **Principle 6.** The scope boundary is enforced by what does not exist. If you
  find yourself adding a free-text box that accepts anything and routes it
  somewhere, stop.
- **Principle 2.** A policy upgrade is an attributable decision, recorded, and
  the person is told before the idea leaves.
- **Principle 3.** The morning shows what the night produced *including* a
  partial night. It never renders an error instead of partial results.
- **Principle 1.** What the interview learns lands in the brain as diffable
  markdown, and the topic-file diff is the learning claim.

## The loop

```bash
git status --short && openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q          # 518 pass today
npm --prefix apps/web run test && npm --prefix apps/web run typecheck
npm --prefix apps/web run build
scripts/check-no-environment.sh && scripts/check-american-english.sh
```

All green before starting. Then propose, clarify, apply, verify, sync, archive.

## Verification

**Automated**, and these must be able to fail:

- The whole interview completes with the microphone permission denied. Assert it,
  because that is principle 4 in one test.
- Answering a question writes the decision with its modality, and a
  `queued-for-tonight` answer is readable as tonight's input.
- A policy-widening answer records `upgrade_decision_id` and
  `policy_source = 'decision-upgrade'`; without a decision, widening is refused.
- The briefing after a partially failed night shows the stages that completed.
- The three morning scenarios from the open decision each render the briefing
  you said they would.

**Visual, and on a real phone.** Screenshot the interview, open the images, and
read them. Then do one interview yourself, out loud if the input half exists, and
report whether it felt like being interviewed or like filling in a form. If it
felt like a form, say so — that is the finding, and it is more useful than a
green suite.

## Quality bar

The code is the submission. Judges read this repository.

**Never ship:** hardcoded questions standing in for `decisions`; lorem text; a
turn that requires a microphone; `any` in TypeScript; a `useEffect` that fetches
without cleanup; an open-ended text box that accepts arbitrary instructions; a
briefing that renders an error instead of partial results.

**Always:** read from the real API; match the existing idiom; keep the capture
PWA working, it takes real ideas; keep provider specifics inside `providers/`.
American English. No hostnames, addresses, usernames or home paths in tracked
files.

## Hard stops

Stop, record the question with your recommendation, and move on:

- A `[NEEDS CLARIFICATION]` marker. Do not answer your own.
- A constitution violation. Blocking, not advisory.
- Anything in `NOT_BUILDING.md` — and the chat interface is the live risk here.
- Credentials, payment, account settings, or anything outward-facing.
- Rewriting published history or force-pushing.

## Report

1. The three morning briefings, and the rule that made none of them confusing.
2. What you decided about voice, and why that is not on the critical path.
3. What shipped, with test counts.
4. **The interview you did yourself** — whether it felt like being interviewed.
   Honestly. If it did not, say so.
5. Anything blocked, with your recommendation.
6. What you would do next, and why that rather than the alternative.
