# 0010 — Brain content carries `local-only`

**Status:** accepted · **Date:** 2026-09-02

## Context

`add-retrieval` had to answer a question no earlier document did: what policy
does a brain topic file carry when retrieval assembles it into context?

Entries carry an explicit `entries.default_policy`, set at capture. Brain topic
files — `profile.md`, `style-guide.md`, `skills/*.md` — carry nothing. They are
distilled by the system from the whole corpus of captured ideas, across every
policy those ideas were captured under, so there is no field to read and no
capture moment to attribute them to.

The constitution says "only assembled, policy-filtered context is ever eligible
to leave" and, separately, "the brain itself never leaves." The first sentence
implies brain-derived context can leave once filtered. The second is a
statement about the store. Neither settles what a *file* distilled from mixed
material inherits.

## Decision

Brain topic files carry `local-only`.

A `local-only` run retrieves them normally. A `cloud-assisted` run does not:
`assemble_context` filters them out before returning, so brain content is never
inside a structure a caller could hand to a remote provider.

This is a default, not a permanent property. Changing it means a new ADR
superseding this one, and a change that argues the case — not a configuration
flag, because a switch that could be flipped is a switch that will be.

## Rationale

**A file distilled from local-only material inherits local-only.** The brain is
written by summarizing across every entry. If any local-only idea contributed
to `profile.md`, then `profile.md` contains local-only material, and there is
no mechanism today that could tell which sentence came from where. Treating the
output as less restricted than its most restricted input would launder the
policy.

**The two directions of error are not equivalent.** Failing closed costs a
cloud-assisted run its brain context: the artifact is less personalized, which
is visible, annoying, and fixable by a later decision. Failing open puts the
user's distilled private material into a Token Factory request, which is not
fixable — the request has already happened. Only one of these is recoverable,
and the airlock exists precisely for the one that is not.

**It is the reading that makes both constitution sentences true.** "Only
assembled, policy-filtered context is ever eligible to leave" still has force:
entry-derived context flows to cloud-assisted runs under exactly that rule.
"The brain itself never leaves" is honored literally rather than narrowly.

## Consequences

- A `cloud-assisted` run assembles from entries alone. On the corpus of
  2 Sep that is 3 of 6 documents; a `local-only` run assembles from all 6.
- The eight-week personalization claim is demonstrated on the `local-only`
  path, which is also the path the demo's `$0.00 cloud spend` artifact runs on.
  The two arguments reinforce rather than compete.
- Reversing this is a visible act: `BRAIN_POLICY` is one constant in
  `retrieval/index.py`, and a test asserts brain content is absent from
  cloud-assisted context. Flipping it turns that test red, which is the point.
- Open, and deliberately not answered here: whether a future capability should
  derive per-file provenance so a topic file distilled only from
  `cloud-assisted` entries could carry `cloud-assisted`. That is a real
  improvement and a larger change than this one — it needs the brain to record
  which entries fed which file, which nothing does today.
