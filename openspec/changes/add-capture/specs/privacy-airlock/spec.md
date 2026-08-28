## ADDED Requirements

### Requirement: What the capture surface was offered is recorded

An entry SHALL record the capability report shown at the moment of capture —
which policies were offered, which were unavailable, and the specific finding
that made each unavailable one unavailable.

Recording only the policy chosen is insufficient. Without the offer, a choice
made because an option was unavailable is indistinguishable from a choice made
freely.

#### Scenario: Chosen under a degraded profile
- **WHEN** an entry is captured as `cloud-assisted` while `local-only` is unavailable
- **THEN** the entry records that `local-only` was offered but unavailable, together with the finding that caused it

#### Scenario: Chosen freely
- **WHEN** an entry is captured as `cloud-assisted` while `local-only` was available
- **THEN** the entry records that both were available, so the choice is attributable to intent

#### Scenario: Preference distinguished from capability after the fact
- **WHEN** the local-versus-cloud token ratio is reported over a period during which the local reasoner was intermittently unreachable
- **THEN** entries captured while `local-only` was unavailable are identifiable, so the ratio is not misread as a change in preference
