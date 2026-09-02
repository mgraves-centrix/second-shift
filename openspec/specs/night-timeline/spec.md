## Purpose

A recorded night, read back and rendered as time: the whole run in one response,
laid out in the lanes it recorded, scrubbed by pointer or keyboard, honest about
how far it got, and read in the timezone the idea was captured in.

## Requirements

### Requirement: A recorded night is readable in one request

A recorded run's timeline SHALL be retrievable as a single response carrying every
event in the run, its lanes, its stages, and the frame it occupies.

Rendering a frame MUST NOT require a further request. Scrubbing across the night
MUST NOT produce a loading state.

The frame SHALL end after the last event *ends*, not where the last event starts.
A run's own `ended_at_ms` MUST NOT be relied on as the frame: nothing closes a run
yet, so it is null on every recorded run.

#### Scenario: The whole night arrives at once
- **WHEN** a run's timeline is requested
- **THEN** every event in that run is returned, together with its lanes, its stages and the frame

#### Scenario: Scrubbing fetches nothing
- **WHEN** the playhead is dragged from the start of the night to the end
- **THEN** every frame along the way is drawn from data already held, and no request is made

#### Scenario: The longest bar fits inside its own night
- **WHEN** an event's duration carries it past the instant the last event starts
- **THEN** the frame still contains it, so it is not drawn beyond the edge of the timeline

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
- **THEN** its payload is returned, together with every model call its invocation made — each with its model, its tokens and its cost

#### Scenario: No single call is guessed at
- **WHEN** an event's invocation made more than one model call
- **THEN** all of them are returned, described as the calls that invocation made rather than as the call behind this event, because an event records no model call id and any single answer would be inferred

#### Scenario: An event with no model call behind it
- **WHEN** detail is requested for an event whose invocation made no model call, or that has no invocation at all
- **THEN** the response says there are none, rather than omitting the field in a way indistinguishable from a call that cost nothing

### Requirement: What a model was told and what it said never leaves through this view

No response in this capability SHALL carry prompt or completion text, or a path to
it. Token counts, costs, latencies and model identifiers are accounting and MAY be
served; the content of a call MUST NOT be.

`model_call_payloads` MUST NOT be joined by any route added here.

#### Scenario: Detail carries accounting, not content
- **WHEN** detail is requested for an event whose invocation made model calls
- **THEN** the models, token counts and costs are returned and no prompt or completion text is, in any field

#### Scenario: The response shape cannot express it
- **WHEN** the detail response is inspected
- **THEN** it has no field a prompt or completion could travel in, so the exclusion does not depend on a handler remembering it

### Requirement: Duration is visible at a glance

An event carrying a duration SHALL render as a bar whose length is that duration.
An event carrying none SHALL render as a tick.

The two SHALL differ in **shape**, not only in size, and a bar SHALL have a
minimum width. Width alone MUST NOT be the only thing that separates them: at a
full-night zoom the median duration is narrower than the tick it must be
distinguished from.

#### Scenario: A bar shorter than a pixel
- **WHEN** an event's duration is too short to occupy a pixel at the current scale
- **THEN** it is drawn at the minimum bar width rather than at its true width, and still rendered with the bar's shape

#### Scenario: A tick is not a very short bar
- **WHEN** an event carrying no duration is rendered beside a bar at minimum width
- **THEN** the two are drawn with different shapes, so neither can be mistaken for the other

#### Scenario: A long crawl reads as long
- **WHEN** an event lasting minutes is rendered
- **THEN** its width is proportional to its duration rather than clamped, so the difference between a long event and a short one survives

### Requirement: Density over time is legible without labels

The rendering SHALL make variation in event density across the night visible
without reading any label.

A quiet hour and a busy one MUST look different.

#### Scenario: A quiet hour beside a busy one
- **WHEN** a night containing both a sparse period and a dense burst is rendered
- **THEN** the two periods are visibly different in the timeline itself, rather than distinguishable only by inspecting individual events

### Requirement: Lanes come from the recorded lane, and nesting from the tree

Events SHALL be laid out in the lane each event recorded. The invocation tree
SHALL supply parentage and depth, so nesting is represented.

A lane MUST NOT be derived by joining an event to the role of the invocation that
produced it. An event may record a lane that differs from its producer's role,
and an event may have no invocation at all.

Depth SHALL be rendered as a visible offset within a lane, distinguishable
between adjacent depths, rather than as additional lanes.

#### Scenario: Concurrent lanes are visible
- **WHEN** two lanes contain events at overlapping instants
- **THEN** both are drawn at those instants in their own lanes, so the overlap is visible without interaction

#### Scenario: An event with no invocation still has a lane
- **WHEN** an event that no invocation produced is rendered, such as a stage boundary
- **THEN** it appears in the lane it recorded rather than being dropped or pooled into an unlabeled remainder

#### Scenario: A recorded lane wins over its producer's role
- **WHEN** an event records one lane while the invocation that produced it has a different role
- **THEN** it is drawn in the lane it recorded, because the lane is a rendering decision made at write time and the role is not

#### Scenario: Nesting is offset, not flattened
- **WHEN** two events in one lane were produced by invocations at different depths
- **THEN** they are drawn at different offsets within that lane, so a call made by a call is visibly inside it

### Requirement: The rendering corresponds to the playhead's instant

What the timeline shows as current SHALL be the events at the playhead's instant,
and no others.

An event SHALL be current while the playhead is within it, and SHALL be rendered
as past once the playhead is beyond it.

#### Scenario: Scrubbing to an instant
- **WHEN** the playhead rests at an instant
- **THEN** the events reported as current are exactly those in progress at that instant, and events at other instants are not among them

#### Scenario: Past and future are distinguishable
- **WHEN** the playhead is part-way through the night
- **THEN** events it has passed are rendered differently from events it has not reached

#### Scenario: A bar is current for its whole duration
- **WHEN** the playhead is inside a bar rather than at its start
- **THEN** that event is still current, because a duration is an interval and not an instant

### Requirement: Scrubbing holds its frame budget

Moving the playhead SHALL update only what changed, not the whole timeline.

A frame during continuous scrubbing SHALL cost no more than the budget for 60
frames per second. A drag that crosses the entire night in one frame is the worst
case and SHALL remain within that budget at the size of night this system
produces.

#### Scenario: A frame updates only what the playhead crossed
- **WHEN** the playhead advances past some events
- **THEN** only those events' rendering changes, rather than every event being rewritten

#### Scenario: The worst case is bounded
- **WHEN** the playhead is dragged across the entire night within a single frame
- **THEN** the frame completes within the 60fps budget

### Requirement: The night is honest at rest

A night SHALL state how far it got, and an event recorded at warning or error
severity SHALL be visually distinct from one recorded at information severity.

Because a run's `outcome` is null until something closes it, how far the night got
SHALL be read from its stages. A night that did not finish MUST NOT render as one
that did.

#### Scenario: A stage still running
- **WHEN** a night whose last stage never completed is shown
- **THEN** that stage is shown as unfinished, rather than the night reading as complete

#### Scenario: A failure is visible without interaction
- **WHEN** a night containing an event recorded at error severity is rendered
- **THEN** that event is visually distinct in the timeline before anything is hovered or clicked

#### Scenario: An absent verdict is not a good one
- **WHEN** a run carries no outcome at all
- **THEN** the night reports what its stages reached rather than presenting the absence as success

### Requirement: The night renders in its own local framing

An instant SHALL be presented in the timezone the idea behind the night was
captured in, not the server's and not the viewer's.

The playhead SHALL expose both the instant it rests on and that timezone.

#### Scenario: A night captured in another zone
- **WHEN** a night whose entry was captured in a different timezone is rendered
- **THEN** its instants read in that zone, so "the frantic bit at 3am" is a claim about where the person was

#### Scenario: The playhead exposes what a later layer needs
- **WHEN** the playhead rests at an instant
- **THEN** both that instant and the night's timezone are available, which is what a celestial layer would need and is why they are carried before it exists

### Requirement: The playhead is operable by keyboard and announced

The playhead SHALL be movable by keyboard, and the moment it rests on SHALL be
announced to assistive technology.

The timeline MUST NOT be operable by pointer alone.

#### Scenario: Arrow keys move the playhead
- **WHEN** the timeline has focus and an arrow key is pressed
- **THEN** the playhead moves to a different instant and what is current changes accordingly

#### Scenario: The moment is announced
- **WHEN** the playhead comes to rest at an instant
- **THEN** that instant is available to a screen reader, politely rather than interrupting

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

No route added by this capability SHALL create, change or delete a row, and the
rendering SHALL offer no control that would.

#### Scenario: Every route added here is a read
- **WHEN** a write is attempted against any route this capability adds
- **THEN** it is refused, because none of them accept one

#### Scenario: Reading changes nothing
- **WHEN** a night is listed, its timeline fetched, and an event's detail fetched
- **THEN** every table holds exactly the rows it held before

#### Scenario: No control to attach a write to
- **WHEN** the rendering is inspected for interactive controls
- **THEN** it offers scrubbing and inspection only, because a timeline that grew a retry or edit control would have become task management
