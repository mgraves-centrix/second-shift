## 1. Fixes

- [x] 1.1 Scope queued answers to their entry, consume them only when a run closes having done something, and return an answered idea to the queue when an answer is queued for tonight.
- [x] 1.2 Show the interviewer only its own run.
- [x] 1.3 Record stage failures and tool calls against their run, and report the interviewer's failure in the briefing.
- [x] 1.4 Refuse to start a night on `cloud` or when a backend cannot be bound; retry that refusal from the unit for an hour.
- [x] 1.5 Recover an interrupted night under a one-night-at-a-time lock.
- [x] 1.6 Guard each entry, catch everything on a stage's write path, and fail a fan-out that landed no file.
- [x] 1.7 Refuse hosts with ports or in punctuation, identifiers, and unlisted opening capitals in the search query.
- [x] 1.8 Accept a retried identical answer; answer a conflicting one with 409.
- [x] 1.9 Resolve an unreachable briefing to `unreachable`, keep API reads out of the service worker's cache, and add the morning's error boundary.

## 2. Gates

- [x] 2.1 Full API suite, web suite, typecheck and build, both check scripts, strict validation.
- [ ] 2.2 `systemd-analyze --user verify` on the night unit, on the always-on machine. Not runnable on the development laptop; owed.
