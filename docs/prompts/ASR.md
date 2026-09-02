# ASR prompt

Paste as the first message of a fresh session. **Requires the Spark** — the
model runs there and nowhere else.

**`MORNING_INTERVIEW.md` defers to this by name. It gates nothing, by design.**

---

Run the ASR spike, then implement `Transcriber`. Read
`openspec/constitution.md`, `CLAUDE.md`,
`docs/decisions/0006-model-bindings.md` and `docs/SPEC_ROADMAP.md` first; they
are the rules, not background.

## Why this one, and why it is allowed to fail

Voice is how an idea gets captured at 3am without finding a keyboard, and
end-of-utterance detection is the genuinely hard part of push-to-talk — the
80–160ms decision that makes a turn feel like a conversation rather than a form.

**But principle 4 makes this optional on purpose.** TTS and ASR must not be on
the critical path of any feature; voice upgrades a working text path and never
gates one. Capture works by typing today and will still work by typing if this
spike fails. **Start by confirming that is still true, and if any part of the
product has quietly come to depend on speech, report it as a violation before
writing any code.**

This is the last unrun spike. Three ran and passed; two of those found that the
published first-party recipe did not work on the version it named. Expect
friction and budget for it.

## What already exists — do not invent any of it

- `Transcriber` — `transcribe(audio, policy=)` public, `_do_transcribe` for you.
  The base class records the event and refuses a remote provider under
  `local-only`; you write no telemetry. `NullTranscriber` returns empty and is
  bound on every profile today.
- ADR 0006 binds **`nvidia/nemotron-speech-streaming-en-0.6b`** — streaming, with
  punctuation and capitalization built in — and **Parakeet Realtime EOU** at
  120M for turn-taking. Neither has ever been run.
- **Spike C left you the environment.** MagpieTTS was verified on the Spark
  2026-08-28, which paid the full dependency cost: NeMo 3.1.0 aarch64, torch
  2.13.0+cu130, CUDA available on GB10. **Python must be pinned to 3.12** —
  NeMo's dependencies cap below 3.14. `peft` is a real import-time dependency
  that `[tts]` omits. The ASR spike inherits all of this rather than paying it.
- Spike B left headroom deliberately: the reasoner runs at
  `--gpu-memory-utilization 0.30`, 43 of 121 GiB, 77 free. MagpieTTS adds 1.85
  GiB on top. **ASR is unmeasured**, and if `RETRIEVAL.md` has landed the embedder
  is also resident — measure against what is actually running, not against Spike
  B's numbers.
- Spike A confirmed `getUserMedia` works on the phone over the Tailscale Serve
  TLS origin, so the browser half of the capture path already works.
- `entries.modality` and `decisions.answer_modality` both have `voice` in their
  CHECK constraints. The schema has been expecting this since day 1.

## The open decision

**Where end-of-utterance runs, and what latency budget it has.**

EOU is the whole reason this is interesting, and it can sit in two places. On the
device, it is instant but must run in a browser. On the Spark, it is a round trip
over the tailnet added to an 80–160ms decision, and the round trip may exceed the
thing being measured.

**Do not decide this by preference.** Measure the tailnet round trip from the
phone to the Spark first — before any model work — and compare it to the EOU
window. If the round trip is 100ms, server-side EOU is not a design, it is a
regression, and you should say so and stop rather than build it.

The second open thing: **whether this ships as a spike or a capability.** If the
spike finds the model does not stream usably on this hardware, the correct output
is `scripts/spikes/spike-e-asr/FINDINGS.md` and no `Transcriber` at all. **A
failed spike that is written up is a success**; two of the three that ran
produced their most useful findings from things that did not work.

## What good looks like

- Push-to-talk in the PWA produces text in an entry, and **the same entry could
  have been typed.** Identical row, identical policy, `modality = 'voice'`.
- The text path is untouched and still works with the microphone denied.
- Transcription runs **locally**. Speech is the most personal data the system
  handles, and a `local-only` idea spoken aloud must never reach a remote
  transcriber.
- Latency is reported as a number a person would recognize: time from releasing
  the button to seeing text.
- Memory is measured **alongside whatever else is resident**, which closes the
  co-residency question Spike B left open for ASR specifically.
- A failure is loud: no transcription is better than a silently wrong one, and a
  wrong transcription of a 3am idea is worse than no capture.

## Scope — what NOT to build

- **No wake word.** `NOT_BUILDING.md` excludes open-mic wake-word listening by
  name — a multi-week always-listening pipeline with nothing demonstrable at the
  end. Push-to-talk is the whole feature at 2% of the cost.
- **No always-on microphone.** The button is the consent.
- **No speaker identification, no diarization.** Single-tenant.
- **No cloud transcription fallback.** Local or nothing.
- **No changes to the interview.** `MORNING_INTERVIEW.md` owns that surface; this
  makes a capability it may or may not use.
- **No blocking anything on this.** If it slips, it slips alone.

## Constitution hooks

- **Principle 4 governs, and it is permission to fail.** Voice layers onto a
  working text path. Nothing may come to require speech, and if you find
  something that has, that is the finding.
- **Principle 2.** Audio and its transcript are captured content. Local
  transcription on every profile; a `local-only` entry's audio never leaves.
- **Principle 7.** The base class records the transcription event. Do not bypass
  it.
- **Principle 6.** No wake words, no always-listening.

## The loop

```bash
git status --short && openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q          # 302 pass today
scripts/check-no-environment.sh && scripts/check-american-english.sh
```

On the Spark, **never `uv run`** — it re-resolves the environment to x86_64 and
destroys it. `python -m venv` plus `pip` with pinned constraints, Python 3.12.

Follow the spike protocol: a question, a measurement, and
`scripts/spikes/spike-e-asr/FINDINGS.md` whether it passes or fails.

## Verification

- **Measure the tailnet round trip before anything else**, and put it beside the
  EOU window. That number decides the architecture.
- Transcribe a known utterance and compare against what was said. Report the
  errors, not an accuracy percentage — a percentage over three samples is
  theater.
- **The text path still works with the microphone denied.** Assert it. That is
  principle 4 in one test, and it must be able to fail: make a turn require audio
  and watch it go red.
- A `local-only` entry's audio reaches no remote provider — assert no remote
  transcriber is constructed, not merely that none was called.
- Resident memory with the reasoner up, and the embedder too if it has landed.
- End-to-end from the phone: hold, speak, release, see the entry. If it feels
  wrong, say so — the latency that matters is the one a person feels, not the one
  the log reports.

## Quality bar

The code is the submission. Judges read this repository.

**Never ship:** a `TODO`; a transcriber that returns a plausible constant; a
cloud fallback; an accuracy number from three samples; a test that passes with
the implementation deleted; anything that makes the text path depend on audio.

**Always:** keep provider specifics inside `providers/`; write the findings
document whether it passed or failed; measure against what is actually resident;
let failures be loud. American English. No hostnames, addresses, usernames or
home paths in tracked files.

## Hard stops

Stop, record the question with your recommendation, and move on:

- A `[NEEDS CLARIFICATION]` marker. Do not answer your own.
- A constitution violation. Blocking, not advisory — **including discovering that
  something already depends on speech.**
- Anything in `NOT_BUILDING.md`. Wake words are the live risk here.
- Credentials, payment, account settings, or anything outward-facing.
- Restarting `nemotron-lightning` is permitted but costs about three minutes of
  reload; do it deliberately and confirm it is serving again.

## Report

1. The tailnet round trip beside the EOU window, and what it decided.
2. Whether this is a spike write-up or a capability. **A failed spike, written
   up, is a complete session** — say so plainly rather than half-shipping.
3. Resident memory with everything else running.
4. What the transcription actually got wrong, in its own words.
5. Whether push-to-talk felt right. **Honestly** — if the latency is bad, that is
   the finding.
6. Anything blocked, with your recommendation.
