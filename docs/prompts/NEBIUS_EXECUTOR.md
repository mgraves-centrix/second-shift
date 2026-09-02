# Nebius executor prompt

Paste as the first message of a fresh session.

**Blocked on credentials and on four decisions, not on code.** The proposal,
design and delta spec already exist at
`openspec/changes/2026-09-02-add-nebius-executor/`. Read them before anything
else — this prompt does not repeat them.

---

Implement `nebius-executor`. Read `openspec/constitution.md`, `CLAUDE.md`,
`docs/decisions/0004-nebius-workload-split.md`, and the existing change
directory first; they are the rules, not background.

## Check first, and stop if either is missing

1. **A Nebius credential.** If there is none, stop. Do not stub it. Every other
   stand-in here is visibly inert — `EchoReasoner` returns its own input — but a
   stub executor returning plausible job results is indistinguishable in
   `model_calls` from a real fan-out, and the fan-out is the entire evidence for
   the Nebius claim.
2. **The four clarification markers, resolved.** Run `/openspec:clarify` against
   the change. They are: the judge deployment target; how a job reaches the
   machine that holds the brain; idempotency when a job reports twice; and
   whether Token Factory has a Batch variant for Lightning and Super
   specifically. **Do not answer your own markers.**

If either check fails, report which and stop. That is a complete session.

## Why this one

It carries every obligation deferred out of day 1, and one of them —
the judge deployment target — is submission-blocking and closes an open risk
recorded in an accepted ADR.

It is also the difference between "uses Nebius" and "needs Nebius." ADR 0004
makes parallel variant generation the argument, because five concurrent builds is
the thing one Spark cannot do.

## What already exists — do not invent any of it

- `Executor.dispatch(job, telemetry=)` / `await_result(handle)`, with
  `InProcessExecutor` behind it as a visibly inert stand-in.
- **`Recorder.ingest_external` is written and tested**, and reading it settles
  more of the transport than it looks. It refuses an unknown dispatching
  invocation, resolves depth so remote work joins the tree at full depth,
  requires invocations parents-first so a partial batch cannot half-write, and
  holds the recorder's lock so ingest serializes through the single writer.
  **Almost every way to get the transport wrong is a way of doing more than
  authenticate, deserialize and call it.**
- `TelemetryDescriptor` carries `ingest_url`, `credential`,
  `dispatching_invocation_id` and `run_id`. `JobResult` carries the work product
  only, and ADR 0004 settled that — telemetry travels its own channel.
- `config/pricing.toml` has Lightning, Super and Ultra, standard and Batch, read
  from the console on 27 Aug. Batch is exactly half of standard across every
  model observed. A missing rate fails loudly; none is missing.
- The design doc records a third transport option the roadmap did not consider:
  the job reports nothing and `await_result`, which already polls, collects the
  telemetry alongside the artifacts. No inbound path exists at all. It costs
  liveness. Weigh it — do not skip past it because two options were named first.

## The open decision — and why none of it is yours

Every decision this capability turns on is already a `[NEEDS CLARIFICATION]`
marker in the change directory. That is unusual and it is deliberate: the judge
deployment target closes a risk in an accepted ADR, and how a job reaches the
machine that holds the brain is a security decision about the machine, not an
implementation detail.

**So the rule here is stronger than elsewhere. Do not decide any of them by
preference, and do not decide them at all.** Run `/openspec:clarify`, take the
answers, and build to them. A marker resolved by assumption launders a guess into
a recorded architectural decision, and these four are the ones most likely to be
quietly rationalized because the code is otherwise ready.

The one judgement that *is* yours: whether the design's third transport option —
the job reports nothing and the poller collects — is still on the table after the
markers resolve. Weigh it on liveness, not on effort.

## What good looks like

- A build stage fans out to real parallel jobs and the artifacts come back
  ranked, with `variant_group` and `variant_rank` populated by the critic.
- Remote telemetry rejoins the invocation tree at full depth. On the scrubber, a
  Nebius job looks like work, not like a gap.
- A job that never returns leaves the run `degraded` with its earlier stages
  intact. Principle 3 does not stop at the network boundary.
- The same work reported twice is recorded once, enforced by the recorder rather
  than trusted to the reporter.
- The cost of a cloud night is readable from `model_calls` without arithmetic,
  because the demo's two-ideas-side-by-side comparison is read from there.

## Scope — what NOT to build

- **No night pipeline changes** beyond substituting the executor.
- **No new telemetry contract.** `ingest_external` is the contract.
- **No public endpoint** unless the security marker resolved that way, on the
  record.
- **No batch reasoning** until the Batch marker resolves — it changes whether a
  batch turn is a `Reasoner` call or an `Executor` job.
- Nothing runs generated code.

## Constitution hooks

- **Principle 2 governs and this is the system's first real egress.** Retrieval
  stays local. Only assembled, policy-filtered context leaves. `local-only` never
  dispatches — refused at the call, unrecordable at the database. **Re-check this
  at every step, not once at the start**; it is the easiest principle to erode by
  convenience once a remote provider exists at all.
- **Principle 5.** Nebius specifics stay in `providers/`. The night sees
  `Executor`.
- **Principle 7.** A dispatched job whose telemetry never arrives leaves the run
  visibly incomplete. It must never look like a job that cost nothing.

## The loop

```bash
git status --short && openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q          # 302 pass today
npm --prefix apps/web run test && npm --prefix apps/web run typecheck
scripts/check-no-environment.sh && scripts/check-american-english.sh
```

All green before starting. The change is already proposed — resolve the markers,
then apply, verify, sync, archive.

## Verification

- A `local-only` run dispatches nothing. Assert the count of jobs is zero, and
  that the guard refuses before anything leaves the process.
- Telemetry from a job attaches under its dispatcher at the right depth; a forged
  or unknown parent writes nothing.
- The same report delivered twice adds no rows.
- A job that times out records a typed failure and the run reaches `degraded`.
- Ingest and local telemetry written concurrently serialize through one writer —
  and the test must be able to fail, so try it with a second connection and watch
  it break.
- Then run **one real fan-out** and paste the costs beside a `local-only` night's
  zero.

## Quality bar

The code is the submission. Judges read this repository.

**Never ship:** a stub that returns plausible job results; a second database
connection for ingest; telemetry inside `JobResult`; a dispatch from inside a
request handler; a credential in a tracked file; a `TODO`.

**Always:** keep provider specifics inside `providers/`; keep writes inside the
recorder's lock; keep tables append-only; let failures be loud. American English.
No hostnames, addresses, usernames or home paths in tracked files.

## Hard stops

- A `[NEEDS CLARIFICATION]` marker. Four are already open. Do not answer them.
- A constitution violation. Blocking, not advisory.
- Anything in `NOT_BUILDING.md`.
- **Credentials.** Use one that is already configured. Never obtain, rotate,
  print or commit one.
- Rewriting published history or force-pushing.

## Report

1. Which markers resolved and how, or that they did not and you stopped.
2. The real fan-out, with its cost beside a local-only night's zero.
3. What shipped, with test counts.
4. Whether the fan-out actually produced better artifacts than one machine
   would have. **If it did not, say so** — the parallelism is the argument, and
   an argument that does not hold is worth knowing before a judge tests it.
5. Anything blocked, with your recommendation.
6. What you would do next, and why that rather than the alternative.
