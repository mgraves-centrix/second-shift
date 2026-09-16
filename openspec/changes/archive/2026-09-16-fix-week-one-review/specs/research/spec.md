## ADDED Requirements

### Requirement: A query refuses addresses, identifiers and unlisted opening names

A span SHALL be judged whole, delimited by any whitespace and stripped of
surrounding punctuation. A host with or without a port or path, a span
containing a digit or underscore, and a hyphenated run too long to be
vocabulary SHALL NOT contribute a term. A capitalized word opening a sentence
SHALL contribute a term only if it is an ordinary opening word.

#### Scenario: A host is refused wherever it sits
- **WHEN** an entry carries a host after a newline, inside parentheses, or with a port
- **THEN** no part of the host appears in the query

#### Scenario: A name that opens a sentence is refused
- **WHEN** an entry opens with a company name, or a name follows an abbreviation
- **THEN** the name does not appear in the query

### Requirement: A search is accounted to its run

A tool call made by a run's research stage SHALL name that run, so the run's
spend is the sum of its calls.

#### Scenario: A run's spend sums by run
- **WHEN** a run's research stage makes several calls
- **THEN** summing tool-call credits for that run gives their total
