## 1. Decisions that come first

Implementation tasks are deliberately absent. Three questions in `proposal.md`
and one in `design.md` each change what gets built rather than how, and a task
list written past them would be a guess wearing a checkbox. They resolve through
`/openspec:clarify`.

No Nebius credential exists in the environment this was written in, so nothing
here could be verified even where it is specified. Nothing is stubbed: a stub
executor returning plausible job results would be indistinguishable in
`model_calls` from the real fan-out that is the evidence for the whole Nebius
argument.

**Both since resolved, 2 Sep.** A Token Factory key confirmed the model
identifiers and exposed that Batch is unavailable — folded into the four
resolutions below. A Nebius Cloud IAM service account
(`<service-account-id>`, project `<project-id>`,
`editor` scoped to that project via a custom group, never the tenant-wide
`editors` group) was created, and its authorized key pair was verified
end-to-end rather than assumed correct from the docs: a hand-built RS256 JWT
(the documented `jwt encode` example omits `iat`; the token endpoint rejects
that) exchanged for a real access token, which then authenticated
`GET /iam/v1/profiles` — confirming the account and its project — and
authorized `GET /ai/v1/jobs?parentId=<project-id>` with a 200
and an empty list, confirming the `editor` grant is live, not just present. The
private key never left the always-on machine; every signing operation ran
there over the tailnet. Both credentials live at
`~/.config/second-shift/secrets.env` and `~/.config/second-shift/keys/` on that
machine, mode 0600, outside any git-tracked path.

- [x] 1.1 Resolve the four clarification markers. Resolved 2 Sep; see the
  resolutions in `proposal.md` and `design.md`.
- [x] 1.2 Record the judge deployment target as a numbered ADR, superseding
  the open risk in ADR 0004 rather than editing it. Recorded as
  `docs/decisions/0009-judge-instance-runs-on-a-no-gpu-serverless-endpoint.md`.
  ADR 0004 itself is untouched — the record of what was open, and for how
  long, stays visible there rather than edited away.
- [x] 1.3 Confirm a Nebius credential is available to the machine, and that it
  is held where a public repository cannot see it. Confirmed for both Token
  Factory and Cloud IAM, verified against the live account rather than
  inspected for shape.

## 2. Then

**Written 21 Sep, now that group 1 has resolved.** Until then this section was
three sentences of prose, which made `openspec list` read the change as
`✓ Complete` — three of three tasks done — while none of the work existed. A
checkbox count is what somebody deciding what to do next actually reads, so
prose here was a status report that said the opposite of the truth.

The sequencing was already fixed by that prose and is unchanged: **telemetry
collection before dispatch**, because a job dispatched before its telemetry can
return is a job whose cost is unrecoverable and whose run is unaccountable; and
**dispatch before the cloud reasoner**, because the reasoner's shape depends on
whether a batch turn is an executor job. The judge instance is no longer last
here — it moved out to `judge-mode` and shipped on 20 Sep.

### Blocked, and on exactly one thing

**Every task below needs a Nebius credential, and the credentials are on the
always-on machine** — `~/.config/second-shift/secrets.env` and
`~/.config/second-shift/keys/`, mode 0600, outside any git-tracked path. They
exist and were verified end to end on 2 Sep. What is missing is a route to where
they are, not a credential.

**`NEBIUS_EXECUTOR.md`'s first hard stop forbids working around that**: if there
is no credential, stop, and do not stub it. Every other stand-in in this system
is visibly inert — `EchoReasoner` returns its own input — but a stub executor
returning plausible job results writes `model_calls` rows indistinguishable from
a real fan-out, and that fan-out is the entire evidence for the Nebius claim.
A session without the credential writes this list and stops, which is what
happened here.

### 2.1 Telemetry collection

- [ ] 2.1.1 `await_result` collects the telemetry the job wrote beside its
      artifacts and calls `Recorder.ingest_external` locally, holding the
      recorder's lock. **No inbound route.** The design argued three transports
      and took the third; `ingest_external`'s own docstring said otherwise until
      21 Sep and now says this.
- [ ] 2.1.2 A deserializer from the job's written form to `ExternalInvocation`
      and `ExternalModelCall`, refusing anything it cannot map rather than
      dropping it — a silently skipped model call is a cloud night that reads
      as cheaper than it was.
- [ ] 2.1.3 Invocations parents-first, so a partially written telemetry file
      cannot half-apply. `ingest_external` already refuses a model call naming
      an unrecorded invocation; this is the ordering that lets it not have to.
- [ ] 2.1.4 The same job collected twice adds no rows. Enforced by the recorder,
      never trusted to the reporter — the spec says so and this is where that
      is proved.
- [ ] 2.1.5 A job whose telemetry is absent or unreadable leaves the run
      identifiable as incomplete, and never as a job that cost nothing.
      Principle 7 does not stop at the network boundary.

### 2.2 Dispatch

- [ ] 2.2.1 A `NebiusExecutor` in `providers/`, implementing `dispatch` and
      `await_result` against Nebius Serverless Jobs. Nothing outside
      `providers/` learns what Nebius is; the night sees `Executor`
      (Principle 5).
- [ ] 2.2.2 Credentials read from the machine's secrets file, never from a
      tracked path and never from a request. A JWT signed RS256 with an explicit
      `iat` — the documented `jwt encode` example omits it and the token
      endpoint rejects that, which cost a session on 2 Sep.
- [ ] 2.2.3 `local-only` never dispatches. Refused at the call by
      `assert_permitted` and unrecordable at the database by the `model_calls`
      CHECK. **Re-checked at every task in this group, not once at the start**:
      this is the system's first real egress and Principle 2 is the easiest to
      erode by convenience once a remote provider exists at all.
- [ ] 2.2.4 Only assembled, policy-filtered context leaves. Retrieval stays
      local on every profile, and the brain never leaves at all.
- [ ] 2.2.5 A build stage fans out to real parallel jobs, and the artifacts come
      back with `variant_group` and `variant_rank` populated by the critic.
      Five concurrent builds is the thing one Spark cannot do, and it is what
      ADR 0004 makes the argument on.
- [ ] 2.2.6 A job that never returns leaves the run `degraded` with its earlier
      stages intact, rather than failing the night.
- [ ] 2.2.7 Remote telemetry rejoins the invocation tree at full depth, so a
      Nebius job renders on the scrubber as work rather than as a gap.

### 2.3 The cloud reasoner

- [ ] 2.3.1 A `Reasoner` for Token Factory covering the turns ADR 0004 assigns
      to it — research synthesis, architect, critic — under `cloud-assisted`
      only.
- [ ] 2.3.2 Standard rates, not Batch. A Token Factory key confirmed on 2 Sep
      that Batch is unavailable for these models; `config/pricing.toml` carries
      both and a missing rate fails loudly.
- [ ] 2.3.3 The cost of a cloud night is readable from `model_calls` without
      arithmetic, because the demo's two-ideas-side-by-side comparison is read
      from there.

### 2.4 Verification, on the machine

- [ ] 2.4.1 One real fan-out, with the rows to show for it: five jobs, five
      results, `variant_rank` set, and a tree the scrubber draws to full depth.
- [ ] 2.4.2 A dispatched job killed mid-flight, and the run left visibly
      incomplete.
- [ ] 2.4.3 The same telemetry collected twice, with no second set of rows.
- [ ] 2.4.4 A `local-only` entry refused at the call, and the refusal recorded.
- [ ] 2.4.5 `python3 scripts/gate.py` green, run unpiped.
