# test-harness

## ADDED Requirements

### Requirement: A push carries a green gate, or is refused

Pushing SHALL be refused when the gate does not pass, rather than left to the
person pushing to have checked.

The refusal MUST name the way to proceed anyway, because an override somebody
cannot find is one they route around by disabling the mechanism entirely.

Removing a branch SHALL NOT be gated: a deletion has no tree to check, and
making it wait is the friction that gets the guard uninstalled.

The guard SHALL be tracked in the repository and enabled deliberately, so that
it is reviewable and arrives with a clone without installing itself.

#### Scenario: The gate is red
- **WHEN** a push is attempted while the gate fails
- **THEN** the push is refused, and what failed is on screen

#### Scenario: The gate is green
- **WHEN** the gate passes
- **THEN** the push proceeds

#### Scenario: Pushing anyway, on purpose
- **WHEN** somebody needs to push past a failure
- **THEN** the refusal has already told them how

#### Scenario: Deleting a branch
- **WHEN** a push removes a branch rather than adding commits
- **THEN** it is not gated, because there is no tree to check
