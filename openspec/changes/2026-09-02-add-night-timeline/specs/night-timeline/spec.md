## ADDED Requirements

### Requirement: A recorded night is readable in one request

A recorded run's timeline SHALL be retrievable as a single response carrying every
event in the run, its lanes, and the run's time frame.

Rendering a frame MUST NOT require a further request. Scrubbing across the night
MUST NOT produce a loading state.

#### Scenario: The whole night arrives at once
- **WHEN** a run's timeline is requested
- **THEN** every event in that run is returned, together with the lanes and the first and last instants of the run

#### Scenario: Scrubbing fetches nothing
- **WHEN** the playhead is dragged from the start of the night to the end
- **THEN** no request is made, because the data needed to draw any frame is already held

#### Scenario: An unknown run
- **WHEN** a timeline is requested for a run that does not exist
- **THEN** the response says so rather than returning an empty night, which would be indistinguishable from a night in which nothing happened

### Requirement: Frame data carries no payload to parse

The timeline response SHALL carry only the pre-rendered scalar columns — instant,
lane, kind, label, severity, duration, and the invocation an event belongs to.

It MUST NOT carry `payload_json`. Detail for a single event SHALL be a separate
request.

#### Scenario: The timeline response is scalar
- **WHEN** a timeline is returned
- **THEN** no event in it carries a payload, so a renderer cannot parse JSON to draw a frame even by mistake

#### Scenario: Detail is fetched for one event
- **WHEN** detail is requested for a single event
- **THEN** its payload and the model call joined through its invocation are returned — the model, its tokens and its cost

#### Scenario: An event with no model call behind it
- **WHEN** detail is requested for an event that no model call is attributed to
- **THEN** the response says there is none, rather than omitting the field in a way indistinguishable from a call that cost nothing

### Requirement: Duration is visible at a glance

An event carrying a duration SHALL render as a bar whose length is that duration.
An event carrying none SHALL render as a tick.

The two MUST be distinguishable at full-night zoom, where a duration below the
median is narrower than a pixel. Width alone MUST NOT be the only thing that
separates them.

#### Scenario: A long crawl and an instant write
- **WHEN** a night containing both a multi-minute event and an instantaneous one is rendered
- **THEN** the two are distinguishable without reading a label

#### Scenario: A bar shorter than a pixel
- **WHEN** an event's duration is too short to occupy a pixel at the current scale
- **THEN** it is still drawn as a bar and still reads as one, rather than collapsing into a tick

### Requirement: Lanes come from the recorded lane, and nesting from the tree

Events SHALL be laid out in the lane each event recorded. The invocation tree
SHALL supply parentage and depth, so nesting is represented.

A lane MUST NOT be derived by joining an event to the role of the invocation that
produced it. An event may record a lane that differs from its producer's role,
and an event may have no invocation at all.

A viewer MUST be able to tell that several agents worked at once, and which
produced the most, without a legend.

#### Scenario: Concurrent agents are visible
- **WHEN** a night in which several lanes were active in overlapping periods is rendered
- **THEN** their lanes show that overlap

#### Scenario: An event with no invocation still has a lane
- **WHEN** an event that no invocation produced is rendered, such as a stage boundary
- **THEN** it appears in the lane it recorded rather than being dropped or pooled into an unlabeled remainder

#### Scenario: A recorded lane wins over its producer's role
- **WHEN** an event records one lane while the invocation that produced it has a different role
- **THEN** it is drawn in the lane it recorded, because the lane is a rendering decision made at write time and the role is not

#### Scenario: Nesting is represented
- **WHEN** an invocation was called by another invocation
- **THEN** that relationship is represented in the rendering rather than flattened away

### Requirement: The night is honest at rest

A run whose outcome was degraded or failed SHALL render as such, and an event
recorded at warning or error severity SHALL be visually distinct.

A degraded run MUST NOT render as a smooth success.

#### Scenario: A failed stage
- **WHEN** a night containing a failure is rendered
- **THEN** the failure is visible in the timeline without interaction

#### Scenario: The run's outcome is stated
- **WHEN** a run that did not complete is shown
- **THEN** its outcome is stated rather than implied by absence

### Requirement: The playhead is operable by keyboard and announced

The playhead SHALL be movable by keyboard, and the moment it rests on SHALL be
announced to assistive technology.

The timeline MUST NOT be operable by pointer alone.

#### Scenario: Arrow keys move the playhead
- **WHEN** the timeline has focus and an arrow key is pressed
- **THEN** the playhead moves and the view follows it

#### Scenario: The moment is announced
- **WHEN** the playhead moves
- **THEN** the instant it now rests on is available to a screen reader, politely rather than interrupting

#### Scenario: The control names itself
- **WHEN** the timeline receives focus
- **THEN** it identifies itself and its current position, rather than being an unlabeled region

### Requirement: A synthetic night says so

A run generated rather than recorded SHALL be rendered, and SHALL be labeled as
synthetic wherever it is shown.

A synthetic night MUST NOT be presentable as evidence of a real one.

#### Scenario: A generated night is shown
- **WHEN** the only recorded nights are generated ones
- **THEN** they are rendered rather than hidden, because a view that shows nothing cannot be verified

#### Scenario: It is labeled
- **WHEN** a generated night is rendered
- **THEN** it is labeled as synthetic on its face, so a screenshot of it cannot be mistaken for a real run

### Requirement: The timeline never writes

The timeline SHALL be read-only. It MUST NOT expose any operation that mutates a
row.

#### Scenario: No write path exists
- **WHEN** the timeline is used in any way
- **THEN** no row is created, changed or deleted, because a timeline that grew a retry or edit control would have become task management
