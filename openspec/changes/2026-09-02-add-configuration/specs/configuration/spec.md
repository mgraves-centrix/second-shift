# configuration

## ADDED Requirements

### Requirement: Every setting the system reads is enumerable

The system SHALL expose a resolved view naming every `SECOND_SHIFT_*` variable
it reads, including those read by shell rather than by Python. A variable read
anywhere in the tree and absent from the view SHALL fail the test suite.

#### Scenario: A variable added without being registered fails the suite
- **WHEN** a module reads a `SECOND_SHIFT_*` variable that the resolved view does not know about
- **THEN** the enumeration test fails, naming the unregistered variable

#### Scenario: A shell-read variable is included
- **WHEN** the resolved view is listed
- **THEN** `SECOND_SHIFT_RUBRIC_OVERWRITE`, which only `deploy/spark/deploy.sh` reads, appears and is marked as read by shell

### Requirement: Every resolved value names where it came from

Each setting in the view SHALL report its origin as the environment, a named
file, or a default. A value originating in a file SHALL name that file by path.

#### Scenario: Environment beats file beats default
- **WHEN** a setting is resolved with the variable set, then with only the file entry present, then with neither
- **THEN** the reported origin is the environment, then that file's path, then the default, and the value matches each source in turn

#### Scenario: A file-sourced value is traceable without reading Python
- **WHEN** a setting resolves from a configuration file
- **THEN** the view names the file, so the value can be corrected without opening a `.py`

### Requirement: The view resolves without the resources it configures

Resolution SHALL NOT require a database, a brain repository, a configuration
file, or a network. Diagnosis that needs the thing being diagnosed is a second
failure, not a diagnosis.

#### Scenario: An empty environment with no configuration files still reports
- **WHEN** the view runs with every `SECOND_SHIFT_*` variable unset and no configuration file present
- **THEN** it prints every setting with its default and exits without raising

#### Scenario: No database is opened
- **WHEN** the view runs
- **THEN** no connection is made to the database and no row is written, including no telemetry row

### Requirement: A secret-shaped value is redacted

A setting whose name marks it as a credential SHALL have its value redacted in
the view rather than printed, while still reporting its origin and whether it
resolved.

#### Scenario: A credential's presence is reported without its value
- **WHEN** a setting whose name ends in `_KEY`, `_TOKEN`, `_SECRET`, or `_PASSWORD` resolves from the environment
- **THEN** the view reports that it is set and where it came from, and does not print the value

### Requirement: A file that exists and cannot be parsed is loud and names itself

Where a configuration file is present but unparseable, the system SHALL raise an
error naming the file. An absent file SHALL continue to yield documented
defaults. A malformed file SHALL NOT be indistinguishable from an absent one.

#### Scenario: A malformed models file is reported rather than defaulted
- **WHEN** `config/models.toml` exists and contains invalid TOML, and the local endpoint is resolved
- **THEN** an error is raised naming `models.toml`, rather than the resolution silently returning the built-in host and port

#### Scenario: A malformed location file is reported rather than yielding no coordinates
- **WHEN** the configured location file exists and contains invalid TOML
- **THEN** an error is raised naming that file, rather than returning empty coordinates

#### Scenario: An absent file still defaults
- **WHEN** a configuration file does not exist and a setting it would supply is resolved
- **THEN** the documented default is returned and the origin is reported as the default

#### Scenario: A malformed pricing file names the file
- **WHEN** the pricing file exists and contains invalid TOML
- **THEN** the raised error names that file's path

### Requirement: The synthetic flag refuses a value it does not recognize

`SECOND_SHIFT_SYNTHETIC` SHALL accept only documented true and false spellings.
An unrecognized value SHALL raise rather than resolve to false.

#### Scenario: A typo does not silently mark seed data as real
- **WHEN** `SECOND_SHIFT_SYNTHETIC` is set to a value that is neither a recognized true nor a recognized false spelling
- **THEN** an error is raised naming the accepted values, rather than resolving to false

#### Scenario: Unset means false
- **WHEN** `SECOND_SHIFT_SYNTHETIC` is not set
- **THEN** the resolved value is false

### Requirement: The exit code reports whether required settings resolved

The command SHALL exit zero when every required setting resolved and non-zero
when one did not, so it can gate a deploy.

#### Scenario: A missing required setting exits non-zero
- **WHEN** a setting marked required does not resolve from environment, file, or default
- **THEN** the command exits non-zero and names that setting

#### Scenario: A fully resolved configuration exits zero
- **WHEN** every required setting resolves
- **THEN** the command exits zero
