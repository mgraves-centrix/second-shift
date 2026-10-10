# Second Shift

**The assistant that interrogates your idea before spending compute on it.**

Second Shift is an always-on personal assistant that turns half-formed ideas into
real artifacts overnight. You capture an idea by voice or text whenever you have
one. Overnight, a machine you own researches it and builds something. In the
morning you ask "what happened since we last talked," get a briefing — and then
it interviews you, asking the questions it got stuck on. Your answers become
tracked decisions that feed the next night's run.

Overnight agents are a commodity. The interview is the product.

Built for the Nebius x NVIDIA Global AI Hackathon, Personal AI track.

---

## Status

**Start with [`docs/SUBMISSION.md`](docs/SUBMISSION.md)** — what this is, what
has been measured, and what has not.

**What exists.** 22 capabilities <!-- derived: count openspec/specs/*/ --> are
specified and shipped across 32 <!-- derived: count openspec/changes/archive/*/ -->
OpenSpec changes: capture, the brain, the night orchestrator, the morning
interview, retrieval, research, agents, the eval harness, configuration, the PWA
with its night scrubber, the judge instance, backup and restore. Those two
directories are the authority on the count — **this sentence said "eighteen" for
three weeks after it stopped being true**, which is why both figures now derive
from the directories and `scripts/check-drift.py` fails the build when they
drift again.

**What is unproven, and why it is one thing and not four.** Four claims have not
been measured: a build stage fanned out to real parallel Nebius Jobs, a cloud
night's cost beside a local one, the week-8 eval score, and the judge container
standing up. Each of them needs a session on the always-on machine, which is
where the credentials and the real data are. `docs/SPEC_ROADMAP.md`'s *Owed
verification* table is the full list, and **nothing is stubbed to fill those
rows**: a stub executor returning plausible job results would write telemetry
indistinguishable from a real fan-out, and that fan-out is the whole evidence
for the Nebius claim.

**What is live.** Capture went live on 28 Aug and has been taking real ideas
since. Two real nights ran against the live reasoner on 16 Sep and a six-of-six
night with research on 17 Sep. The entry count is in the database on that
machine, not in this repository, so this file does not quote one.

Nothing here asks to be taken on trust:

```bash
npx openspec list --specs     # the capabilities, from the specs themselves
cat docs/SPEC_ROADMAP.md      # what is built, what is owed, and to whom
python3 scripts/gate.py       # 11 gates <!-- derived: matches scripts/gate.py ^    \(" -->, the ones CI runs
```

This section was a 22-row table of hand-written milestone states until 10 Oct,
and three of its rows were wrong by then — one still read "never run against the
real reasoner" three weeks after two nights had. It is the week-one record it
always was, and it now sits at the end of
[`docs/WEEK_ONE.md`](docs/WEEK_ONE.md) beside the plan it reports on.

---

## The loop

```
capture ──▶ queue ──▶ night run ──▶ artifacts + open questions
   ▲                                          │
   │                                          ▼
decisions ◀────────────── morning interview ◀─┘
```

Each stage of the night run commits as it completes. If the 2am build stage
fails, morning still has the brief, the research, and the questions. Graceful
degradation is correct behavior, not a failure state.

---

## Scope

**Idea in, artifact out, memory in between.**

That boundary is load-bearing. See [NOT_BUILDING.md](NOT_BUILDING.md) for what
is deliberately excluded and why.

---

## Architecture principles

1. **The brain is a folder of plaintext under git.** Skills, style guide,
   failure ledger, profile — human-readable markdown, diffable across time.
   No opaque memory database.
2. **Privacy Airlock.** Every idea carries a policy set at capture:
   `local-only` (never leaves the machine) or `cloud-assisted` (redaction pass,
   then Nebius Token Factory). Retrieval always runs locally; only assembled,
   policy-filtered context is ever transmitted. The brain itself never leaves.
3. **No empty mornings.** The night pipeline is a checkpointed state machine.
   Every stage that completes is committed and presentable.
4. **Text-first, voice layered on.** Every voice interaction has a working text
   equivalent.
5. **Two deployments, one codebase.** Personal instance on owned hardware;
   judge instance on Nebius with a synthetic persona and zero real data,
   labeled in-UI as a demo.

---

## Stack

| Layer | Technology |
|---|---|
| Capture | PWA — Next.js / React, Web Audio API |
| ASR | Nemotron Speech Streaming 0.6B, local |
| Local reasoning | Nemotron 3.5 Lightning 30B A3B (NVFP4), vLLM |
| Cloud reasoning | Nemotron 3 Super / Ultra via Nebius Token Factory |
| Overnight compute | Nebius Serverless Jobs |
| Judge demo hosting | Nebius |
| Web research | Tavily |
| Embeddings | Llama Nemotron Embed VL 1B v2, local |
| Memory | Plaintext markdown + SQLite, git-versioned |
| Orchestrator | Python + FastAPI, SQLite job queue, systemd timers |
| Dashboard | Next.js + Tailwind, server-sent events |
| TTS | MagpieTTS via NeMo Speech — non-blocking |

Target hardware: NVIDIA DGX Spark (GB10 Grace Blackwell, 128GB unified memory,
aarch64, CUDA 13.0, sm_121).

Every model in the runtime path is an NVIDIA open model. See
[docs/MODELS.md](docs/MODELS.md) for exact bindings and
[THIRD_PARTY.md](THIRD_PARTY.md) for licenses.

---

## Telemetry

Every agent invocation and every model call is logged from run one — provider,
model, tokens, latency, cost, and the privacy policy it ran under. This is not
housekeeping. It is how the Privacy Airlock is proven rather than claimed
(local-only ideas consume visibly zero cloud tokens), and how "it gets better at
being me" becomes a measurable trend instead of an assertion.

---

## Getting started

Python 3.12 and Node 20+. Every command runs from the repository root.

```bash
python3.12 -m venv apps/api/.venv
apps/api/.venv/bin/pip install -c apps/api/constraints.txt -e "apps/api[dev]"
apps/api/.venv/bin/pip install -e packages/seed
npm --prefix apps/web install
```

The suites and the two source checks:

```bash
apps/api/.venv/bin/python -m pytest apps/api/tests -q
npm --prefix apps/web run test && npm --prefix apps/web run typecheck
scripts/check-no-environment.sh && scripts/check-american-english.sh
```

To see a night without a GPU, credentials or a network, generate a synthetic one
and point the API at it:

```bash
apps/api/.venv/bin/python -m secondshift_seed --seed 42 --db /tmp/night.db
SECOND_SHIFT_DB=/tmp/night.db SECOND_SHIFT_PROFILE=cloud SECOND_SHIFT_SYNTHETIC=1 \
  apps/api/.venv/bin/uvicorn secondshift.api.main:app --port 8080
npm --prefix apps/web run dev
```

`SECOND_SHIFT_SYNTHETIC=1` is not optional and was missing here until 19 Sep.
The seeded rows carry the flag already; anything *captured* against an instance
stood up without it is written `is_synthetic = 0` — a real-looking row on the
deployment that is supposed to hold none. The parser is strict, so a typo raises
at startup rather than quietly resolving to "real".

Every row it writes carries `is_synthetic = 1`, and the rollup views exclude
them, so a generated night can never be mistaken for a real one.

Never run `uv run` on the DGX Spark: it re-resolves the environment for the
wrong architecture and destroys it. Use the virtual environment above.

---

## License

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
