# frontend

## ADDED Requirements

### Requirement: Every surface is reachable without typing a URL

A person who opens the root SHALL be able to reach every built surface by
following links, and SHALL be able to tell what the product is from the first
screen.

#### Scenario: The capture surface links onward
- **WHEN** the capture screen is opened and scrolled
- **THEN** links to the other built surfaces are present and followable

#### Scenario: A desktop surface links back
- **WHEN** a desktop surface is opened
- **THEN** it carries navigation to the other surfaces including capture

### Requirement: Capture carries no chrome above its content

The capture surface SHALL NOT place navigation or other chrome above the idea
input, because vertical space above the fold is what the privacy choice competes
for when a keyboard is open.

#### Scenario: The policy choice is not pushed further down by navigation
- **WHEN** the capture screen is rendered at a keyboard-up viewport
- **THEN** the policy options are no lower than they are without navigation

#### Scenario: Onward links do not occupy space above the input
- **WHEN** the capture screen is rendered
- **THEN** its onward links appear after the capture control, not before the input

### Requirement: Design tokens are declared in one place

Every color token SHALL be declared in a single file that all surfaces consume.
No component stylesheet SHALL declare its own color.

#### Scenario: A component stylesheet declares no color token
- **WHEN** the component stylesheets are inspected
- **THEN** none of them declares a color custom property of its own

#### Scenario: Adding a surface requires no new color
- **WHEN** a new surface is built from the token file
- **THEN** it can be styled without declaring a color of its own

### Requirement: Capture's styling does not apply to other surfaces

Capture's layout and control styling SHALL be scoped to capture. Global styles
SHALL be limited to the reset, the type ramp and the tokens.

#### Scenario: A button outside capture does not inherit capture's button
- **WHEN** a control is rendered on a surface other than capture
- **THEN** it does not receive capture's full-width button styling

#### Scenario: Capture renders identically after scoping
- **WHEN** the capture screen is rendered before and after the styles are scoped
- **THEN** the two renderings are identical

### Requirement: The judge instance is labeled from served data

Where the resolved compute profile identifies a demo deployment, the interface
SHALL say so, driven by data the API serves rather than by a build-time flag.

#### Scenario: A cloud profile is labeled a demo
- **WHEN** the served capability report resolves the profile as `cloud`
- **THEN** the interface displays a demo label

#### Scenario: A local profile is not labeled
- **WHEN** the profile is not `cloud`
- **THEN** no demo label is displayed

#### Scenario: The label needs no separate build
- **WHEN** the same built artifact is served on either deployment
- **THEN** the label appears or not according to the served report

### Requirement: Every surface works at narrow and wide viewports

Surfaces SHALL be usable from 320px to 1920px without horizontal scrolling.

#### Scenario: No horizontal overflow at the narrowest supported width
- **WHEN** a surface is rendered at 320px wide
- **THEN** its content does not overflow horizontally
