# Retrieval prompt

Paste as the first message of a fresh session. Local to build; the Spark to
measure, because the embedder has to be co-resident with the reasoner.

**Independent of everything except the schema. Can run in parallel with
`CONFIGURATION.md`, `AGENTS.md`, `FRONTEND.md` and `TEST_HARNESS.md`.**

---

Build `retrieval`. Read `openspec/constitution.md`, `CLAUDE.md`,
`docs/decisions/0002-no-vector-database.md` and `docs/SPEC_ROADMAP.md` first;
they are the rules, not background.

## Why this one

Retrieval is where the Privacy Airlock stops being a policy and becomes a
mechanism. Principle 2 says retrieval happens locally **on every compute
profile**, and that only assembled, policy-filtered context is ever eligible to
leave. Nothing implements that yet — `HashEmbedder` returns deterministic noise.

It is also what makes the brain worth having. The eight-week claim is that the
system gets better at being you; without retrieval, memory is a directory nobody
reads.

## What already exists — do not invent any of it

- **ADR 0002 forbids a vector database.** Brute-force cosine over a small corpus.
  This is decided; do not reopen it, and do not add a dependency that smuggles
  one in.
- The `Embedder` interface: `embed(texts, policy=)` public, `_do_embed` for you
  to implement. The base class records the event; you write no telemetry.
- `HashEmbedder` is the placeholder — deterministic, dependency-free, and bound
  on every profile today. It stays, for tests.
- The binding is `nvidia/llama-nemotron-embed-vl-1b-v2`, ~1.7B, **2048-dim**,
  NVIDIA Open Model License, per ADR 0006 and `docs/MODELS.md`.
- Spike B left headroom on purpose: the reasoner runs at
  `--gpu-memory-utilization 0.30`, holding 43 of 121 GiB and leaving 77 free.
  Co-residency with the embedder was the whole argument for NVFP4 — but it is
  **measured for the reasoner only**. The embedder's actual footprint is unknown.
- The brain is markdown under git on the always-on machine: `profile.md`,
  `style-guide.md`, `skills/*.md`, plus a dated journal. `BrainRepo` reads it,
  including `topic_files_at(sha)` for a specific commit.

**There is no embedding storage in the schema.** Sixteen tables and none of them
holds a vector. This is the only capability in the queue that needs a migration,
which makes it the one place where "tables are append-only" and "migrations are
the authority on the data model" both bite.

## The open decision

**Where the index lives.**

ADR 0002 settled *no vector database* — and, in the same paragraph, that
"embeddings are stored as `BLOB`s in SQLite." This prompt read that as leaving
storage open. It did not. The three options below were live questions, but
choosing anything other than the first was a supersession, and shipping it as
though it were not is the defect **ADR 0011** now records. Whichever is chosen,
if it is not a table, it needs a new ADR before it ships:

- A table means a migration, append-only semantics, and vectors in every backup.
- A file means the database and the index can disagree after a crash.
- In-memory means startup cost proportional to the corpus, every time.

**Do not decide this by preference.** Measure it: embed the real corpus — 4
entries and the brain's topic files, which is genuinely small — and report the
vector count, the bytes, and the rebuild time. If rebuilding takes under a
second, the argument for persisting anything is weak and you should say so.
Bring the numbers to the proposal.

## What good looks like

- Retrieval runs locally on **every** profile, including `cloud`. There is no
  configuration that routes it to a hosted embedding endpoint, because principle
  2 forbids one and a switch that could be flipped is a switch that will be.
- Assembly returns a bounded, ordered context, and the caller can see **why**
  each piece is in it — score, source, and the policy it carries.
- Policy filtering happens **before** assembly returns, not at the provider. A
  `local-only` entry's text is never in a structure that a remote call could
  serialize.
- The brain is read at a commit, not from the working tree, when a run pins one.
- Brute force is honest: state the corpus size at which it stops being fine, with
  the measurement behind the number.

## Scope — what NOT to build

- **No vector database.** No FAISS, no Chroma, no pgvector, no `sqlite-vss`.
  ADR 0002, and `NOT_BUILDING.md` defers vector search "only when keyword +
  recency retrieval demonstrably falls over." **That condition was never
  evaluated** — keyword + recency retrieval does not exist, so nothing fell
  over, and the capability shipped cosine search anyway. The line above was in
  this prompt while that happened. Read `NOT_BUILDING.md` for the open question,
  and do not treat a deferral condition as satisfied because a prompt quoted
  it.
- **No reranker.** Optional, week 4+, per `docs/MODELS.md`.
- **No chunking framework.** A brain file is small; split on headings if you must
  split at all.
- **No research.** Retrieval reads what the system already knows.
- Do not put model identifiers in `.py` — they live in `config/models.toml`.

## Constitution hooks

- **Principle 2 governs, and this is the sharpest test of it in the codebase.**
  Retrieval local on every profile; only assembled, policy-filtered context
  eligible to leave; the brain itself never leaves. A violation here looks like:
  an embedding call to a hosted endpoint, raw entry text in an outbound payload,
  or a redaction step that configuration can skip.
- **Principle 1.** The brain is the source of truth and the index is an index
  over it — never the other way round. Deleting the index must lose nothing.
- **Principle 7.** The embedder's base class records its event. Do not bypass it.

## The loop

```bash
git status --short && openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q          # 302 pass today
npm --prefix apps/web run test && npm --prefix apps/web run typecheck
scripts/check-no-environment.sh && scripts/check-american-english.sh
```

All green before starting. Then propose, clarify, apply, verify, sync, archive.

**Never run `uv run` on the Spark** — it re-resolves the environment to x86_64
and destroys it. `python -m venv` plus `pip` with pinned constraints.

## Verification — the airlock test is the one that matters

- **A `local-only` entry's text never appears in anything eligible for egress.**
  Assemble context for a `local-only` entry, then assert the assembled structure
  contains no substring of the raw text. Make it able to fail: remove the filter
  and watch it go red. This is the test the whole principle rests on.
- Retrieval on the `cloud` profile still runs locally — assert no remote provider
  is constructed, not merely that none was called.
- The index over a known corpus returns the obviously-right document for an
  obviously-matching query, and a stable order for ties.
- Reading the brain at a pinned commit returns that commit's content, not HEAD's.
- Deleting the index and rebuilding produces the same results.
- On the Spark: embed the real corpus with the real model, and report resident
  memory **alongside the reasoner**, because that is the only number that
  answers the co-residency question Spike B left open.

## Quality bar

The code is the submission. Judges read this repository.

**Never ship:** a `TODO`; a similarity function returning a plausible constant; a
test that passes with the implementation deleted; a mock of the thing under test;
a policy filter that can be disabled by configuration; a vector store that
becomes the source of truth.

**Always:** match the surrounding idiom; write the test that would have caught
the bug; keep provider specifics inside `providers/`; keep tables append-only;
let failures be loud. American English. No hostnames, addresses, usernames or
home paths in tracked files.

## Hard stops

Stop, record the question with your recommendation, and move on:

- A `[NEEDS CLARIFICATION]` marker. Do not answer your own.
- A constitution violation. Blocking, not advisory — and principle 2 is the one
  this capability is most likely to cross.
- Anything in `NOT_BUILDING.md`.
- Credentials, payment, account settings, or anything outward-facing.
- Rewriting published history or force-pushing.

## Report

1. The measurement that settled where the index lives — vectors, bytes, rebuild
   time — and what you chose.
2. The embedder's resident memory on the Spark **with the reasoner up**, which
   closes Spike B's open co-residency question.
3. What shipped, with test counts.
4. The corpus size at which brute force stops being fine, and how you know.
5. Anything blocked, with your recommendation.
6. What you would do next, and why that rather than the alternative.
