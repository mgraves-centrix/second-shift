# api-layer Specification

## Purpose
The shape of the HTTP surface, so that adding a route is a one-file change and
moving one is provably not a behavior change. Every route lives in the module
its capability owns; the exported web surface is mounted after all of them,
because it answers everything that reaches it and a route behind it is a route
nobody can call. The response models' deliberate absences are the Privacy
Airlock expressed as a type — there is no field prompt or completion text could
travel in — and nothing here authenticates or versions, because every consumer
is deployed with the API on the one origin the always-on machine owns. If that
stops being true, the capability with the new consumer carries the guard or the
prefix on its own router, and no other module changes.

## Requirements

### Requirement: A route lives in the module its capability owns

Each HTTP route SHALL be declared in the module belonging to the capability it
serves, and a capability's routes SHALL be declared in exactly one module.

Adding a route MUST require adding or touching one route module, and MUST NOT
require editing a module belonging to another capability.

A route module MUST NOT import another route module. Translation shared between
capabilities belongs in a module neither of them owns.

#### Scenario: A capability adds a route
- **WHEN** a new route is added for a capability that already has a module
- **THEN** exactly one route module changes, and no other capability's module is edited

#### Scenario: A new capability adds its first route
- **WHEN** a capability with no module yet adds a route
- **THEN** it adds one module and registers it, and no existing route module changes

#### Scenario: Two capabilities need the same translation
- **WHEN** two route modules would both convert the same record into the same response
- **THEN** the translation lives outside both, because a route module importing another is the collision this structure exists to remove

### Requirement: Splitting the layer does not change a single response

Reorganizing where a route is declared SHALL NOT change what it returns.

For every route that existed before the reorganization, the status code, the
headers that carry content type, and the response body MUST be byte-identical
for the same request against the same data.

Equality MUST be asserted by a test that is demonstrated capable of failing,
because a comparison written against the code it tests passes trivially when the
capture is wrong.

#### Scenario: Every route answers as it did
- **WHEN** each route is called against a fixed database before and after the reorganization
- **THEN** the responses are byte-identical

#### Scenario: The comparison can fail
- **WHEN** a field in a response model is renamed
- **THEN** the comparison fails, proving it is comparing something

#### Scenario: A test that builds an application is not rewritten
- **WHEN** the reorganization lands
- **THEN** tests that construct a context and an application directly pass unmodified, because a test that had to change means the contract changed

### Requirement: The static surface is served last, and losing that is loud

The exported web surface SHALL be mounted after every API route, so that an API
path is matched before the mount.

A registration that would leave the mount ahead of a route MUST fail at
application construction rather than at request time.

The ordering MUST be covered by a test that calls an API route and asserts it
receives an API response, because the symptom of wrong ordering is a working
page returned to a caller that wanted data.

#### Scenario: A route is registered after the mount
- **WHEN** the application is constructed with a route registered after the static mount
- **THEN** construction fails, naming the ordering as the reason

#### Scenario: An API path is not answered by the page
- **WHEN** an API route is requested
- **THEN** the response is that route's, not the exported page

### Requirement: The API has no authentication and no version prefix

The API SHALL NOT authenticate requests and SHALL NOT carry a version prefix in
its paths, for as long as every consumer is deployed with it and reaches it on
the origin it serves.

Where authentication becomes necessary, it SHALL be scoped to the capability
that needs it rather than applied across the layer, and no route outside that
capability may be enrolled in or exempted from it.

Where a version prefix becomes necessary, it SHALL be introduced by the
capability with the consumer that needs it, and MUST NOT be applied to routes
whose only consumer is deployed with the API.

#### Scenario: A guard is scoped to one capability
- **WHEN** a capability requires its routes to be authenticated
- **THEN** the guard is declared on that capability's module alone, and adding it does not touch another capability's routes

#### Scenario: A version is introduced for a consumer that needs one
- **WHEN** a consumer exists that is not deployed with this API
- **THEN** the capability serving it introduces the prefix on its own routes, and the routes serving the co-deployed surface keep their paths

#### Scenario: No principal is introduced
- **WHEN** authentication is considered for this layer
- **THEN** nothing is built that requires a request to name a user, because accounts are excluded by the scope boundary

### Requirement: A response carries no field that model call payloads could travel in

The response models SHALL NOT gain a generic passthrough, an envelope, or any
field capable of carrying prompt or completion text, and the absences that
already express this MUST survive any reorganization of the layer.

A route MUST NOT read `model_call_payloads`.

#### Scenario: The absences survive a refactor
- **WHEN** the layer is reorganized
- **THEN** the timeline response still has no payload field and the event detail response still has no field prompt or completion text could occupy

#### Scenario: A generic passthrough is proposed
- **WHEN** a change would add a field that accepts arbitrary content into a response
- **THEN** it is refused, because the airlock here is enforced by the type having nowhere to put it

### Requirement: A route writes through the recorder or does not write

A route that records anything SHALL write through the recorder held on the
request context.

A route module MUST NOT open a database connection.

#### Scenario: A route records an event
- **WHEN** a route records telemetry
- **THEN** it does so through the recorder, under the one writer's lock

#### Scenario: A route module reaches for a connection
- **WHEN** a route module would open its own connection to the database
- **THEN** it is refused, because a second writer is a second writer wherever it is declared
