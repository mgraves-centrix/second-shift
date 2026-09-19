# judge-mode

## ADDED Requirements

### Requirement: A stranger learns what the product is from the first screen

The surface a visitor reaches first SHALL state what the product does before it
asks for anything. It SHALL NOT present an input as the first and only element.

#### Scenario: The first screen explains before it asks
- **WHEN** a visitor opens the root of the judge deployment
- **THEN** the screen says what the product does without the visitor scrolling or typing

#### Scenario: The explanation is not a second build
- **WHEN** the same built artifact is served on the personal deployment
- **THEN** whether the explanation appears is decided by the served capability report, not by a build flag

### Requirement: The judge instance is this code, with no real data

The judge instance SHALL run the same code as the personal instance, separated
only by compute profile.

It MUST contain zero real data, MUST be labeled in-UI as a demo, and every row it
holds MUST be marked synthetic so it can never contaminate a measurement.

#### Scenario: The same code
- **WHEN** the judge instance runs
- **THEN** it differs from the personal instance by compute profile alone, with no demo-only branch in business logic

#### Scenario: Its data is excluded from measurement
- **WHEN** a rollup or an eval reads the tables
- **THEN** the judge instance's rows are excluded, because they are marked synthetic

#### Scenario: A viewer is told what they are looking at
- **WHEN** the judge instance is opened
- **THEN** it says it is a demo

### Requirement: Every accumulating table a judge instance writes is marked synthetic

Where a deployment is synthetic, every row it accumulates SHALL carry that
marking, including rows written by evaluation runs.

#### Scenario: An eval run on a synthetic deployment is marked
- **WHEN** an evaluation runs on a deployment configured synthetic
- **THEN** the rows it writes are marked synthetic rather than entering the measurement unmarked

#### Scenario: A measurement excludes them
- **WHEN** results are read for a curve or a rollup
- **THEN** rows from a synthetic deployment are excluded

### Requirement: Raw payloads never reach a judge deployment

Content captured for local-only ideas SHALL NOT be present in a judge
deployment, and the exclusion SHALL be enforced rather than documented.

#### Scenario: A deployment package omits the payloads
- **WHEN** a judge deployment is assembled
- **THEN** it contains no raw prompt or completion content, and the check that ensures this can fail

### Requirement: The demonstration runs without a reasoner

The judge instance SHALL present a complete night without executing one, because
no reasoner is bound on its profile.

#### Scenario: A recorded night is what is shown
- **WHEN** a visitor asks to see what a night produces
- **THEN** a recorded night is presented, rather than one being executed

#### Scenario: A live run is not offered where it cannot happen
- **WHEN** the deployment's profile binds no reasoner
- **THEN** no control offers to execute a night
