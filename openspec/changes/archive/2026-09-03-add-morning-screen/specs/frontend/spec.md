# frontend

## MODIFIED Requirements

### Requirement: Every surface is reachable without typing a URL

A person who opens the root SHALL be able to reach every built surface by
following links, and SHALL be able to tell what the product is from the first
screen. A surface is built when it has a route; adding one SHALL require
registering it in the shared surface list rather than editing each shell.

#### Scenario: The capture surface links onward
- **WHEN** the capture screen is opened and scrolled
- **THEN** links to the other built surfaces are present and followable

#### Scenario: A desktop surface links back
- **WHEN** a desktop surface is opened
- **THEN** it carries navigation to the other surfaces including capture

#### Scenario: A new surface reaches both shells at once
- **WHEN** a route is added to the shared surface list
- **THEN** it appears in the desktop navigation and in capture's footer without either being edited

#### Scenario: Every registered surface has a route
- **WHEN** the surface list is compared against the routes that exist
- **THEN** every registered surface resolves to a built page
