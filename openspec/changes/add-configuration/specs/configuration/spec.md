## Purpose

Settings as one declared surface: where each value comes from, what happens when
it is wrong, and when that is discovered.

Requirements dependent on the three open questions — name migration, a secrets
layer, and snapshot-versus-reload — are deliberately absent and land once those
are answered.

## ADDED Requirements

### Requirement: Precedence is stated once and applies to every setting

Every setting SHALL resolve as environment, then file, then default. An empty
environment value MUST be treated as unset, for every setting without exception.

#### Scenario: Environment overrides file
- **WHEN** a setting has a value in both the environment and its file
- **THEN** the environment value is used

#### Scenario: An empty environment value is unset
- **WHEN** a setting's environment variable is present but empty
- **THEN** it falls back to the file, and then to the default, exactly as if it were absent

#### Scenario: No value anywhere
- **WHEN** a setting is absent from the environment and its file
- **THEN** its declared default is used, and the resolved source reports that it came from the default

### Requirement: A malformed file is distinct from a missing one

A configuration file that cannot be parsed SHALL produce a named failure
identifying the file and the parse error. It MUST NOT be reported as absent, and
MUST NOT silently yield defaults.

#### Scenario: Malformed file
- **WHEN** a configuration file contains a syntax error
- **THEN** the failure names that file and the error, and does not present as a missing value

#### Scenario: Missing file
- **WHEN** a configuration file does not exist
- **THEN** its settings take their declared defaults without any failure

#### Scenario: A parse error does not misattribute a capability
- **WHEN** the models configuration cannot be parsed
- **THEN** the reported reason names the parse failure, not an absent model — so a capability report does not tell a user the wrong cause

### Requirement: Failure timing is declared per setting

Each setting SHALL declare when a bad value is discovered: refuse to start, fail
at use, or degrade to a default.

Settings whose wrong value would corrupt a measurement that cannot be backfilled
MUST refuse to start. Settings a running system can proceed without MUST NOT
take it down.

#### Scenario: A setting that corrupts measurement refuses to start
- **WHEN** the deployment identity setting holds a value that is neither clearly true nor clearly false
- **THEN** the system refuses to start rather than assuming a default, because the wrong assumption writes permanently mislabeled rows into append-only tables

#### Scenario: An unavailable brain does not take down capture
- **WHEN** the brain location points somewhere unusable
- **THEN** capture continues to succeed and the failure surfaces when the brain is used

#### Scenario: A rendering setting degrades
- **WHEN** the location setting is absent or unusable
- **THEN** the system runs and the dependent rendering degrades, rather than startup failing

### Requirement: Voice never blocks anything

The voice setting SHALL be exempt from startup validation. An unset, unknown or
unusable voice MUST degrade to text at every layer and MUST NOT raise.

#### Scenario: No voice configured
- **WHEN** no voice is set
- **THEN** the system starts, and anything that would speak presents its text equivalent

#### Scenario: A voice that does not exist
- **WHEN** a voice is set to a value the speech stack does not provide
- **THEN** the system starts, the text equivalent is presented, and the unusable voice is reported without raising

#### Scenario: Voice is absent from startup validation
- **WHEN** settings are validated at startup
- **THEN** the voice setting is not among those that can prevent startup

### Requirement: Deployment identity is declared, validated and visible

Whether a deployment is synthetic SHALL be a declared setting, validated at
startup, and reported to clients so a demo deployment can label itself.

It MUST NOT be inferred from an unrecognized value, and MUST NOT be accepted
from a request.

#### Scenario: An unparseable identity refuses to start
- **WHEN** the deployment identity holds an unrecognized value
- **THEN** the system refuses to start, rather than treating it as a real deployment

#### Scenario: A demo deployment is identifiable by a client
- **WHEN** a client requests the system's capabilities on a synthetic deployment
- **THEN** the response identifies it as a demo, without any deployment-specific branch in the handler

#### Scenario: A real deployment is identified as real
- **WHEN** a client requests capabilities on a real deployment
- **THEN** the response identifies it as not a demo

### Requirement: Resolved configuration is inspectable, and safe to share

The system SHALL report every setting's resolved value and where that value came
from — environment, file, or default.

Values declared secret or personal MUST be redacted. Redaction is by
declaration, never by matching a name.

The report MUST state which process environment it resolved under, because
different services set different variables.

#### Scenario: Sources are reported
- **WHEN** resolved configuration is inspected
- **THEN** each setting shows its value and whether it came from the environment, a file, or its default

#### Scenario: Secrets are redacted by declaration
- **WHEN** a setting declared secret is inspected
- **THEN** its value is redacted, and it is redacted because it was declared so rather than because its name looked sensitive

#### Scenario: Personal values are redacted
- **WHEN** settings holding personal data such as coordinates are inspected
- **THEN** they are redacted by default, so the output can be pasted into a document without publishing them

#### Scenario: The reporting context is stated
- **WHEN** resolved configuration is inspected
- **THEN** the report states which process environment produced it, so a value read in a shell is not mistaken for the value a service uses

### Requirement: Policy enforcement is not configurable

Privacy policy enforcement and redaction SHALL NOT be exposed as settings. No
configuration value may disable, weaken or bypass them.

#### Scenario: No setting weakens the airlock
- **WHEN** the configuration surface is inspected
- **THEN** it exposes no setting that disables or relaxes policy enforcement or redaction
