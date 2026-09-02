# Research prompt

> **✅ Shipped 2 Sep — `openspec/changes/archive/2026-09-02-add-research`.**
> Kept as the record of what was asked. Three things to carry forward:
>
> 1. **There was no credential, and the instruction to stop was honored in
>    substance rather than in letter.** Its stated reason — a stub is
>    indistinguishable from a real search in `tool_calls`, and credits are a
>    scored artifact — is satisfied: nothing that fabricates results is
>    importable from `providers/`, and with no credential the stage skips, so
>    **zero rows** exist. The provider is real and has never made a call.
> 2. **Its open decision was answered, and the answer changed the design.**
>    Redaction is construction, not filtering, because category 8 — verbatim
>    phrasing — is a leak no filter can address.
> 3. **The leak list was not run against the real four entries.** They are on
>    the always-on machine. The corpus is synthetic and adversarial by
>    construction, and the real check is still owed.

Paste as the first message of a fresh session. Needs a Tavily credential —
**check for one before planning any code.**

**Depends on `RETRIEVAL.md` and `NIGHT_PIPELINE.md`, both shipped 2 Sep.
`ARTIFACTS.md` also shipped, so the "must not both be in `secondshift/night/`"
collision is settled rather than avoided: `artifacts` lives in its own package
and the night calls it.**

---

Build `research`. Read `openspec/constitution.md`, `CLAUDE.md`, and
`docs/SPEC_ROADMAP.md` first; they are the rules, not background.

## Why this one

Research is the only stage where the system talks to the open internet, which
makes it the only stage where a half-formed 3am idea can leak verbatim to a third
party. `docs/DATA_MODEL.md` and the constitution both name the same failure by
name: **raw entry text in a Tavily query.**

The schema was built expecting this. `tool_calls.query_redacted` is not called
`query` — the column name is the requirement, and its comment says *the raw query
is never stored*. Nothing had written that column until this capability did.

## What already exists — do not invent any of it

- `tool_calls`: `tool`, `endpoint` CHECK over `search`, `extract`, `crawl`,
  `research`; `query_redacted`; `policy` CHECK; `credits`; `result_count`;
  `latency_ms`; `cached`; `outcome` CHECK over `success`, `error`, `quota`.
- `Recorder.record_tool_call(tool=, endpoint=, policy=, query_redacted=,
  credits=, result_count=)` exists and is tested. You call it; you do not
  reimplement it.
- `ToolQuotaExceeded` is already in the failure taxonomy and `classify()` maps a
  message containing quota, rate-limit, 429 or "credits exhausted" to
  `tool_quota`. Raise the typed exception; the ledger handles the rest.
- The airlock's `redaction_applied` flag exists on `model_calls` and the
  quarantine path is built.
- **The synthetic generator writes zero tool calls under `local-only`**, and the
  commit that established it says why: *a search carries the idea off the machine
  as surely as a completion does*. That is the behavior you are implementing, and
  there is already a test asserting the generator honors it.

## Check first, and stop if it is absent

Look for a Tavily credential before anything else. If there is none, **write the
proposal and stop there — do not stub it.** A stub that returns plausible search
results is indistinguishable in `tool_calls` from a real search, and the credit
accounting is a scored artifact.

Every other stand-in in this codebase is visibly inert; `EchoReasoner` returns
its own input. Keep that property.

## The open decision

**What redaction actually removes, and how it is proven.**

"Redact before egress" is a requirement, not an algorithm. A query built from an
entry about a named client, a named employer and an unreleased product is not
made safe by stripping an email address.

**Do not decide this by preference, and do not write a regex and call it done.**
Decide it by writing the adversarial list first: take the four real entries in
the database and the brain's `profile.md`, and enumerate what a search query
derived from each would leak. Then design to that list, and keep it as the test
corpus. Put the list in the proposal.

> **That corpus was not reachable when this shipped, and the substitute is
> labeled rather than passed off.** The development container's database holds
> zero entries and `../second-shift-brain` is absent; the four real entries live
> on the always-on machine. The real subject-authored text that *is* in the
> repository — `config/evals/candidates.md` — is pre-sanitized, because the
> repository is public and `scripts/check-no-environment.sh` enforces it, so a
> redaction test against it would pass with redaction deleted. A deliberately
> adversarial synthetic corpus was built instead, one entry per leak category.
> **Re-run the list against the real four when the machine returns** — that is
> the check this substitute cannot perform.

The second open thing: **who builds the query.** A model turning an idea into
search terms is itself an egress path if it runs remotely — under
`cloud-assisted` the entry text reaching Token Factory to *produce* the query is
the same disclosure as the query itself. Say where query construction runs.

## What good looks like

- A `local-only` run makes **no tool call at all**. Not a redacted one. None.
- Every recorded tool call has a `query_redacted` that a person can read next to
  the entry it came from and agree is safe. That comparison is the test.
- The raw query is never stored, never logged, never in a payload file.
- Credits are accounted per call and per run, and a run's research spend is
  readable without arithmetic.
- Quota exhaustion is a typed failure that degrades the night rather than ending
  it — principle 3 applies here like everywhere.
- A cached result is marked cached and does not spend credits twice.

## Scope — what NOT to build

- **No crawl-the-web-at-large.** `search` and `extract` are the endpoints the
  night needs; `crawl` is in the CHECK but does not have to be used.
- **No second search provider.** One tool, recorded honestly.
- **No result caching layer beyond the `cached` flag** unless the measurement
  says you need one.
- **No summarization here** — that is an agent's turn, recorded as a model call,
  not a tool call.
- Nothing here executes anything it fetched.

## Constitution hooks

- **Principle 2 governs, and this is where it is most likely to be broken.**
  Retrieval stays local; only assembled, policy-filtered context is eligible to
  leave; the redaction step **must not be skippable by configuration**. A flag
  that turns redaction off is a violation even if it defaults to on.
- **Principle 3.** A quota wall degrades the night; the morning still shows what
  the earlier stages produced.
- **Principle 7.** Every tool call is recorded with the policy it ran under.

## The loop

```bash
git status --short && openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q          # 473 pass today
npm --prefix apps/web run test && npm --prefix apps/web run typecheck
scripts/check-no-environment.sh && scripts/check-american-english.sh
```

All green before starting. Then propose, clarify, apply, verify, sync, archive.

## Verification — the leak test, and it must be able to fail

- **Take the real entries. Build the queries. Assert no query contains any
  distinctive substring of its source entry.** Then remove the redaction and
  watch it go red. If that test cannot fail, you have not tested redaction.
- A `local-only` run writes **zero** rows to `tool_calls`. Assert the count, not
  the shape.
- The raw query appears nowhere: not in `tool_calls`, not in `events`, not in
  `model_call_payloads`, not in a log line. Grep the database for it in the test.
- Quota exhaustion records `tool_quota` and the run reaches `degraded`, not
  `failed`.
- Credits sum per run and match the individual calls.
- Exercise against a stub tool so the suite is hermetic and spends nothing.

## Quality bar

The code is the submission. Judges read this repository.

**Never ship:** a `TODO`; a redaction function that returns its input; a test
that passes with the implementation deleted; a stub that produces convincing
search results; a configuration flag that disables redaction; a raw query written
anywhere.

**Always:** match the surrounding idiom; write the test that would have caught
the bug; keep provider specifics inside `providers/`; keep writes inside the
recorder's lock; let failures be loud. American English. No hostnames,
addresses, usernames or home paths in tracked files.

## Hard stops

Stop, record the question with your recommendation, and move on:

- A `[NEEDS CLARIFICATION]` marker. Do not answer your own.
- A constitution violation. Blocking, not advisory.
- Anything in `NOT_BUILDING.md`.
- **Credentials.** Including the Tavily key: use one that is already configured,
  never obtain, rotate or commit one.
- Rewriting published history or force-pushing.

## Report

1. The adversarial leak list, and what redaction does to each item.
2. Where query construction runs, and why that is not itself an egress path.
3. What shipped, with test counts.
4. A real query beside the entry it came from, so the redaction can be judged by
   reading rather than by assertion.
5. Anything blocked, with your recommendation.
6. What you would do next, and why that rather than the alternative.
