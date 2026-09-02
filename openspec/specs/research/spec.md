# research Specification

## Purpose
The only stage that talks to the open internet, and therefore the only place a
half-formed idea can leave the machine verbatim. A search query is *constructed*
from topical terms rather than filtered out of the entry, so the raw text is
never a candidate to become a query; a `local-only` run makes no call at all;
and the path that builds a query exposes nothing that could weaken it.

## Requirements

### Requirement: A local-only run makes no external tool call

Where a run's effective policy is `local-only`, no external search SHALL be
attempted and no `tool_calls` row SHALL be written — not a redacted one, none. A
search carries the idea off the machine as surely as a completion does.

#### Scenario: A local-only night records zero tool calls
- **WHEN** a run whose effective policy is `local-only` reaches the research stage
- **THEN** the count of `tool_calls` rows for that run is zero

#### Scenario: The refusal happens before a query is built
- **WHEN** a `local-only` run reaches the research stage
- **THEN** no query is constructed from the entry text, and the stage records why it was skipped

### Requirement: A query is constructed, never derived from raw text

A search query SHALL be assembled from extracted topical terms. The entry's raw
text SHALL NOT be sent, and SHALL NOT be reachable as a query by any code path,
parameter or configuration.

#### Scenario: No distinctive phrase from the entry reaches the query
- **WHEN** a query is built from an entry containing a distinctive multi-word phrase
- **THEN** that phrase does not appear in the query

#### Scenario: A named third party does not reach the query
- **WHEN** an entry names a client, employer, product codename or person
- **THEN** that name does not appear in the query

#### Scenario: A credential-shaped string is never sent
- **WHEN** an entry contains a token that looks like an API key or secret
- **THEN** it does not appear in the query, in any recorded row, or in any log

#### Scenario: The query is readable beside its entry and defensible
- **WHEN** a query and the entry it came from are read side by side
- **THEN** the query expresses the topical question without carrying identifying material

### Requirement: Redaction cannot be disabled

The query-construction path SHALL expose no parameter, flag or configuration key
that weakens or bypasses it. A switch defaulting to safe is still a switch.

#### Scenario: The function takes no bypass argument
- **WHEN** the query-construction function's signature is inspected
- **THEN** it accepts only the source text, with no parameter capable of selecting a weaker path

### Requirement: Only the redacted query is ever stored

The raw query and the raw entry text SHALL NOT appear in `tool_calls`, in
`events`, in a model-call payload, or in any log line.

#### Scenario: The raw text appears nowhere in the database
- **WHEN** a research call has been recorded and the whole database is searched for a distinctive phrase from the source entry
- **THEN** it is found in `entries` only, and in no other table

#### Scenario: The recorded query is the redacted one
- **WHEN** a tool call is recorded
- **THEN** the stored `query_redacted` is the constructed query

### Requirement: Every tool call is attributable and accounted

Each tool call SHALL record the policy it ran under, its credits, its result
count and its outcome. A run's research spend SHALL be derivable by summing its
tool calls rather than read from a stored total.

#### Scenario: A recorded call carries the run's policy
- **WHEN** a search is recorded
- **THEN** its policy is the policy the run resolved under

#### Scenario: A run's spend is the sum of its calls
- **WHEN** several searches are recorded for one run
- **THEN** the run's research credits equal the sum of the individual calls

#### Scenario: A cached result spends nothing
- **WHEN** a result is served from cache
- **THEN** the call is marked cached and records zero credits

### Requirement: Quota exhaustion degrades the night rather than ending it

Where the search provider refuses on quota grounds, a typed failure SHALL be
recorded and the run SHALL continue to its later stages.

#### Scenario: A quota refusal is typed
- **WHEN** the provider refuses on quota grounds
- **THEN** a failure of type `tool_quota` is recorded

#### Scenario: The night still reaches degraded
- **WHEN** the research stage fails on quota and other stages complete
- **THEN** the run's outcome is `degraded` rather than `failed`

### Requirement: An absent credential produces no call and no fabricated result

Where no search credential is configured, the research stage SHALL record that it
was skipped and SHALL NOT write a `tool_calls` row. No component SHALL return
search results that did not come from the provider.

#### Scenario: No credential means no row
- **WHEN** the research stage runs with no credential configured
- **THEN** the stage is skipped with a recorded reason and no `tool_calls` row exists

#### Scenario: Nothing in the shipped package fabricates results
- **WHEN** the providers package is inspected
- **THEN** no component returns search results other than by calling the provider
