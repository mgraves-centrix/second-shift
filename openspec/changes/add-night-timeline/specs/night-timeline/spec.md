## Purpose

One night, readable as game film: a scrubable timeline of what ran, when, in
which lane, and what it cost — read-only, and honest about a night that is not
finished.

Both open questions are settled: an event links to its model call explicitly,
and the axis covers the run with the evening's captures shown beside it.

## ADDED Requirements

### Requirement: Playback order is by time, then identity

Events SHALL be ordered and paged by timestamp then identifier. The integer
identifier alone MUST NOT be treated as monotonic in time.

#### Scenario: Concurrent agents write out of identifier order
- **WHEN** a night contains nested invocations whose children are recorded after their siblings but occurred earlier
- **THEN** the timeline presents them in time order, not identifier order

#### Scenario: Paging does not skip or repeat
- **WHEN** a window is fetched in pages
- **THEN** every event appears exactly once, including events sharing a timestamp

### Requirement: The axis spans work, not just instants

The timeline's extent SHALL include the end of every bar, computed from each
event's timestamp plus its duration.

#### Scenario: A long bar near the end of the night
- **WHEN** the final events include work lasting far beyond the last recorded instant
- **THEN** the axis extends to cover it, rather than clipping it at the last timestamp

#### Scenario: A degenerate span
- **WHEN** a run contains no events, one event, or several events sharing one instant
- **THEN** the view renders a minimum span rather than dividing by a zero-width axis

### Requirement: The axis is in the timezone the idea was captured in

Wall-clock labels SHALL use the offset recorded with the entry at capture, not
the server's timezone and not the viewer's.

The stored numeric offset MUST be used rather than resolving the zone name at
read time.

#### Scenario: A night captured in another timezone
- **WHEN** a night's entry was captured at a different offset from the viewer's
- **THEN** the axis reads in the capture offset, so 02:00 on the axis is 02:00 where the idea was had

#### Scenario: A daylight-saving boundary
- **WHEN** the night crosses a daylight-saving transition
- **THEN** labels derive from the offset recorded at that instant, so the hour shown is the hour that occurred

### Requirement: Lanes are a stable roster

The set of lanes SHALL come from the run as a whole, not from whichever events
are currently visible.

#### Scenario: Scrubbing past a sparse lane
- **WHEN** a lane holds only one event for the entire night and the view scrubs away from it
- **THEN** the lane remains present and empty, rather than disappearing and reflowing the others

#### Scenario: Lane identity is meaningful
- **WHEN** lanes are displayed
- **THEN** each corresponds to an agent role, and an invocation's lane is derivable without reading its payload

### Requirement: Overlapping work is legible

Where bars within a lane overlap in time, they SHALL be packed so that each
remains visible. A bar spanning a whole stage MUST NOT hide the work drawn
within it.

#### Scenario: Concurrent siblings in one lane
- **WHEN** several invocations of the same role run at overlapping times
- **THEN** each is separately visible rather than drawn on top of the others

#### Scenario: A stage lead spanning its children
- **WHEN** a lead invocation's bar covers the entire window its children occupy
- **THEN** the children remain visible

### Requirement: Work with extent reads differently from instants

An event carrying a duration SHALL render as a bar; one without SHALL render as
a tick, distinguishable at a glance without reading a label.

A bar MUST remain visible at a minimum width when zoomed out, so brief work does
not vanish.

#### Scenario: A crawl and a file write
- **WHEN** a forty-second extraction and an instantaneous write appear together
- **THEN** the two are visually distinct without inspecting either

#### Scenario: Brief work zoomed out
- **WHEN** the whole night is in view and a bar would be narrower than a pixel
- **THEN** it renders at a minimum width rather than disappearing

### Requirement: The run's skeleton is rendered, not dropped

Events not attributable to any invocation SHALL still be rendered.

#### Scenario: Stage boundaries
- **WHEN** stage-start and stage-end events carry no invocation
- **THEN** they appear on the timeline, because they are the structure the rest hangs on

### Requirement: A night still running renders as a correct partial

The view SHALL render a run with no end time as in flight — completed stages
shown as complete and the running one as running — rather than as an error, a
spinner, or an unbounded axis.

#### Scenario: Five stages complete and one running
- **WHEN** a run has no recorded end and its final stage is still running
- **THEN** the completed stages render as complete, the running stage as unfinished, and the axis is bounded by the work that exists

### Requirement: Zooming out preserves severity

Where events are aggregated for display, the aggregate SHALL carry the strongest
severity present, never an average or the most common.

#### Scenario: One error among many routine events
- **WHEN** a bucket contains a single error and many informational events
- **THEN** the bucket presents as containing an error

### Requirement: Rendering never parses payloads

Drawing a frame SHALL use scalar columns only. Detailed payloads MUST be fetched
on demand for a single event.

#### Scenario: A dense night renders
- **WHEN** a night of over a thousand events is scrubbed
- **THEN** no payload is parsed to produce a frame

### Requirement: The timeline is read-only

The view SHALL offer no action that modifies any record. It MUST NOT expose
controls to retry, re-run, edit, annotate or delete.

#### Scenario: No per-event action
- **WHEN** an event's detail is displayed
- **THEN** it offers no control that writes

### Requirement: The timeline is operable without a pointer

The scrubber SHALL expose slider semantics, be movable by keyboard, and announce
the moment it is positioned at in local wall-clock time.

An equivalent reading of the night's events MUST be available as text rather
than only as a drawn timeline.

#### Scenario: Keyboard scrubbing
- **WHEN** the scrubber has focus and arrow keys are pressed
- **THEN** the position moves and the new moment is announced

#### Scenario: Reduced motion
- **WHEN** the viewer prefers reduced motion
- **THEN** automatic playback does not run, and scrubbing remains available

### Requirement: A seeded night is identifiable as seeded

The timeline SHALL distinguish generated rows from real ones, and the deployment
SHALL report whether it is a demonstration.

#### Scenario: A seeded night beside real work
- **WHEN** a generated night and real work share a database
- **THEN** the generated events are identifiable as generated

#### Scenario: A demonstration deployment
- **WHEN** a client asks a synthetic deployment about its capabilities
- **THEN** the response identifies it as a demonstration, so the interface can say so

### Requirement: Cost shown is cost recorded

Any cost presented SHALL be summed from recorded model calls rather than from
measurement views that exclude generated rows.

Where the cost shown is generated rather than real, it MUST be labeled as such.

#### Scenario: Cost on a demonstration deployment
- **WHEN** a wholly synthetic deployment displays what a night cost
- **THEN** a figure is shown rather than a blank, and it is labeled as generated

### Requirement: The playhead exposes an absolute instant

The playhead SHALL expose the absolute instant it is positioned at, together
with the night's location where one is recorded.

#### Scenario: The instant is absolute
- **WHEN** the playhead is read by another component
- **THEN** it reports an absolute time and the capture offset, not a fraction of the axis

### Requirement: An event carries a link to the work behind it

An event produced by a model call SHALL record which call it was, so the call's
model, tokens, latency and cost are reachable exactly rather than inferred.

Correlation by invocation and timestamp MUST NOT be used: more than one call can
share an instant, so it identifies the wrong call without any indication.

#### Scenario: Hover reports the call that produced the event
- **WHEN** an event produced by a model call is inspected
- **THEN** the model, token counts, latency and cost reported are those of that call

#### Scenario: Two calls in one millisecond
- **WHEN** one invocation produces two model calls at the same instant
- **THEN** each event resolves to its own call rather than to whichever is found first

#### Scenario: An event with no call behind it
- **WHEN** an event that was not produced by a model call is inspected
- **THEN** it reports no call, rather than the nearest one

### Requirement: The captures that caused the night are visible

The view SHALL show the entries captured before the run, distinct from the run's
own span.

The scrubable axis MUST remain the run itself, so the timeline is not mostly
empty time.

#### Scenario: The evening's captures
- **WHEN** a night is displayed for a run whose entry was captured earlier that evening
- **THEN** that capture is shown before the run's span, identifiable as a capture rather than as run work

#### Scenario: Scrubbing does not enter the gutter
- **WHEN** the playhead is dragged toward the earliest point
- **THEN** it stops at the run's start, because there is no night before it to scrub
