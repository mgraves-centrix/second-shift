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

- [ ] 1.1 Resolve the four clarification markers.
- [ ] 1.2 Record the judge deployment target as a numbered ADR, superseding the open risk in ADR 0004 rather than editing it.
- [ ] 1.3 Confirm a Nebius credential is available to the machine, and that it is held where a public repository cannot see it.

## 2. Then

Written once group 1 resolves, in this order — the sequencing is certain even
though the contents are not:

Telemetry ingest before dispatch, because a job dispatched before its telemetry
can return is a job whose cost is unrecoverable and whose run is unaccountable.
Dispatch before the cloud reasoner, because the reasoner's shape depends on
whether a batch turn is an executor job. The judge instance last, because it is
this code on a resolved profile and needs the rest to exist first.
