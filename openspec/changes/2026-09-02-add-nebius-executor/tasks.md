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
- [ ] 1.2 Record the judge deployment target as a numbered ADR, superseding the
  open risk in ADR 0004 rather than editing it. **Blocked on a correction, not
  the credential.** The proposal's resolution asserted Nebius Serverless
  Endpoints only serve models; Nebius's own docs describe them as hosting
  arbitrary containers, and the Jobs docs confirm no-GPU container VMs are a
  supported configuration. The cost argument for a CPU target likely survives;
  the reasoning for it does not, and needs rewriting before this ADR is written
  on top of it.
- [x] 1.3 Confirm a Nebius credential is available to the machine, and that it
  is held where a public repository cannot see it. Confirmed for both Token
  Factory and Cloud IAM, verified against the live account rather than
  inspected for shape.

## 2. Then

Written once group 1 resolves, in this order — the sequencing is certain even
though the contents are not:

Telemetry ingest before dispatch, because a job dispatched before its telemetry
can return is a job whose cost is unrecoverable and whose run is unaccountable.
Dispatch before the cloud reasoner, because the reasoner's shape depends on
whether a batch turn is an executor job. The judge instance last, because it is
this code on a resolved profile and needs the rest to exist first.
