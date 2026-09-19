# nebius-executor

## REMOVED Requirements

### Requirement: The judge instance is this code, with no real data

**Reason**: moved to the `judge-mode` capability, which owns the judge
deployment and is where the requirement is implemented and verified.

**Migration**: the requirement is added verbatim by `2026-09-19-add-judge-mode`,
with the synthetic-containment and first-screen requirements it needs beside it.
Nothing is lost; it stops being claimed by two changes at once, which would have
meant whichever archived second duplicated or silently overwrote the other. This
change remains parked on its Nebius credential and keeps every requirement about
dispatching work off the machine.
