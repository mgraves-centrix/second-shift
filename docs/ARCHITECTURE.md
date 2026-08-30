# Architecture

## The portability problem, and why it improves the design

The DGX Spark is the development machine. It is not a requirement of the
product, and building as though it were would produce something only one person
on earth can run.

So the Spark is treated as a **capability tier**, not a platform. Every piece of
compute sits behind one of four interfaces:

```
Transcriber   speech  -> text
Reasoner      prompt  -> completion + token accounting
Embedder      text    -> vector
Executor      job     -> artifact
```

A **compute profile** binds those four interfaces to concrete implementations.
Resolution order: `SECOND_SHIFT_PROFILE` env var, else a boot-time capability
probe (CUDA present? vLLM reachable? NeMo importable?), else `cloud`.

| | `spark` | `workstation` | `cloud` |
|---|---|---|---|
| Transcriber | Nemotron Speech 0.6B, local | Nemotron Speech 0.6B, local | hosted ASR |
| Reasoner (local-only policy) | Lightning 30B via vLLM | Lightning 30B via vLLM | **unavailable** |
| Reasoner (cloud-assisted) | Lightning local, Super/Ultra via Token Factory | Token Factory | Token Factory |
| Embedder | Nemotron Embed 1B, local | Nemotron Embed 1B, local | Token Factory embeddings |
| Executor | Nebius Serverless Jobs | Nebius Serverless Jobs | Nebius Serverless Jobs |
| Night trigger | systemd timer | systemd timer | scheduled job |

### The consequence that makes this a feature

On the `cloud` profile, `local-only` is **not available**. The app says so, in
the UI, plainly — it does not silently downgrade the policy and run the idea
through a remote model anyway.

> **Local-only is a hardware capability, not a preference.**

That is the honest version of a privacy claim, and it is more convincing than a
toggle. A judge sees a product that knows the difference between a guarantee it
can make and one it cannot.

### The efficiency this buys

The judge demo instance *is* the `cloud` profile in a container. Portability
work and submission work are the same work, done once. Anyone can
`docker compose up` and run Second Shift without owning a Spark; the same image
is what gets deployed for judging.

---

## Repository layout

```
second-shift/
├── docs/
│   ├── ARCHITECTURE.md          this file
│   ├── DATA_MODEL.md
│   ├── WEEK_ONE.md
│   ├── NEBIUS_USAGE.md          evidence doc for the judging criterion
│   └── decisions/               numbered ADRs
├── apps/
│   ├── api/                     FastAPI orchestrator (Python)
│   │   └── secondshift/
│   │       ├── config.py        profile resolution + capability probe
│   │       ├── db/              schema.sql, migrations, repository layer
│   │       ├── telemetry/       recorder + contextvar invocation tree
│   │       ├── providers/       base interfaces + one module per backend
│   │       ├── airlock/         policy resolution + redaction
│   │       ├── agents/          roster + versioned prompt files
│   │       ├── night/           checkpointed stage machine
│   │       ├── morning/         briefing + interview
│   │       ├── brain/           markdown read/write + git operations
│   │       ├── retrieval/       embedding index + assembly
│   │       └── api/routes/
│   └── web/                     Next.js PWA + dashboard
│       └── components/
│           ├── scrubber/        the signature component — built once, used three times
│           └── charts/
├── packages/
│   └── seed/                    synthetic night generator
├── deploy/
│   ├── spark/                   systemd units
│   ├── tailscale/               Serve config
│   └── nebius/                  container + job definitions
└── scripts/
```

Python dependencies are managed with `python -m venv` + `pip` against a pinned
constraints file. **`uv run` is never used on aarch64** — it re-resolves the
environment to x86_64 and destroys it. `uv pip install` into an already-active
venv is acceptable; the `run` subcommand is not.

---

## What runs where, and why

The split is decided by what each side is uniquely good at. Nothing is sent to
Nebius to satisfy a rule, and nothing is kept local out of habit.

### Always local — never leaves the machine

- Capture, ASR, transcript and audio storage
- **Embedding and retrieval, unconditionally.** The brain is indexed and
  searched locally on every profile. Only the assembled, policy-filtered
  context is ever eligible to leave.
- Redaction and policy resolution — by definition these must run before egress
- Orchestrator, job queue, stage machine, every database write
- The dashboard and PWA
- All reasoning for `local-only` entries

### Nebius Token Factory — deep reasoning on cloud-assisted entries

The research synthesis, architect, and critic turns. These are long-context,
high-quality-bar calls where a small local model is genuinely the wrong tool:
synthesizing twenty Tavily extracts into a brief is work for Super, not for a
30B model with 3B active. This is a capability argument, not a compliance one.
Exact bindings: [MODELS.md](MODELS.md).

### Nebius Serverless Jobs — parallel variant generation

The build stage fans out **3–5 variants in parallel, one Job each**, and the
critic ranks them into a `variant_group`.

This is the strongest available use of Serverless Jobs because it is something
the Spark *cannot* do. One box cannot run five builds concurrently at speed.
The parallelism is not decorative — it is the reason the artifact is better.
Nightly eval runs dispatch the same way.

### Nebius — judge instance

The `cloud` profile in a container, seeded with a synthetic persona and zero
real data, labeled in-UI as a demo.

> **Open, must be resolved in week one:** Serverless Endpoints appear to be for
> serving *models*, not arbitrary web applications. If that is correct, the
> judge instance needs a container or VM target instead. This is a
> submission-blocking assumption and it gets a spike on day 4, not week 7.

### The demo moment this split produces

Two ideas, side by side on one screen:

- A `local-only` idea that produced a real artifact, with cloud spend of
  **$0.00** — the Airlock proven by instrumentation rather than asserted.
- A `cloud-assisted` idea that fanned out to five parallel Nebius Jobs and
  produced a visibly better artifact for a few cents.

Both claims are read straight off `model_calls`. Neither is a sentence in a
README.

---

## Principles, restated as constraints

| Principle | How it is enforced |
|---|---|
| Brain is plaintext under git | Separate repository on the always-on machine, beside the database the orchestrator writes. The API shells out to git; no memory in an opaque store. |
| Privacy Airlock | `CHECK` constraint on `model_calls` — a local-only row cannot name a remote provider. The write aborts. |
| No empty mornings | `run_stages` rows commit independently; the morning brief is a query over whatever reached `complete`. |
| Text-first | Every voice path has a text sibling route. TTS is never on a critical path. |
| One codebase, two deployments | Compute profiles. The judge instance is a profile, not a fork. |
| One origin | The always-on machine serves the API and the exported PWA together. A development machine is `127.0.0.1` only — a second origin means a second database, and a capture written to the wrong one. (ADR 0009) |
