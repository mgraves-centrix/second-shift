## MODIFIED Requirements

### Requirement: Events are renderable without parsing

The system SHALL write `events` rows with pre-rendered `lane`, `kind`, `label`
and `severity` columns. Detailed payloads MUST be stored separately so that
timeline rendering never requires parsing JSON.

Reading a timeline SHALL accept a time window, so a dense night is fetched in
bounded pieces rather than in full. The projection MUST carry whether each row
is generated, so seeded and real work are distinguishable in one database.

#### Scenario: Dense night playback
- **WHEN** the night view requests events for a six-hour run
- **THEN** every row needed to draw the timeline is available from scalar columns without reading `payload_json`

#### Scenario: A bounded window
- **WHEN** a portion of a night is requested
- **THEN** only events within that window are returned, ordered by time then identifier

#### Scenario: Generated rows are marked
- **WHEN** a timeline is read from a database holding both generated and real work
- **THEN** each row carries whether it was generated
