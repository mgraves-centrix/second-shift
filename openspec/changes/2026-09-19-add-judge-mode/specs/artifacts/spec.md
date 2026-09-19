# artifacts

## ADDED Requirements

### Requirement: A produced artifact can be read back

An artifact the night wrote SHALL be retrievable by the interface that lists it,
so that "idea in, artifact out" is demonstrable rather than described.

#### Scenario: An artifact is fetched by identity
- **WHEN** an artifact recorded for a run is requested
- **THEN** its content is returned

#### Scenario: A missing file is refused, not faked
- **WHEN** an artifact row names a file that is not on disk
- **THEN** the request is refused rather than answered with empty content

#### Scenario: A request cannot escape the artifact root
- **WHEN** a request names a path outside the artifact root
- **THEN** it is refused
