# evals

## ADDED Requirements

### Requirement: A judge drives a model through the provider interface

There SHALL be a judge that grades an output by asking a model for scores,
implemented against the reasoner interface rather than against one provider.
A judge bound to a particular backend would make the grading model a code change
and would put a model identifier outside the provider package.

Its reported name SHALL be the model's own, read at runtime from the provider,
so the name recorded against a run is the model that graded it.

The policy the judge's call runs under SHALL be named at the call site, never
defaulted. The airlock asserts it on every completion, and a judge that could
run without a policy being chosen is a remote call nobody decided to make.

#### Scenario: The judge grades through a reasoner
- **WHEN** a judge scores an output
- **THEN** it completes through the reasoner interface, and the model call is recorded by the provider layer before the judge reads the text

#### Scenario: The run records the grading model by name
- **WHEN** a run is scored
- **THEN** the judge's name is the model identifier the provider reports, not a value written in the judge

#### Scenario: A judge with no policy
- **WHEN** a judge is constructed
- **THEN** the policy its calls run under is a required argument, so no judge can complete without one having been chosen

### Requirement: A judgement is read from an object, never from prose around it

The judgement SHALL be the last top-level JSON object in the completion, parsed
as structured data. Anything else MUST be refused as an unreadable judgement.

This is one rule rather than a tolerance. The served checkpoint emits its
deliberation inconsistently — sometimes inside a delimiter, sometimes as bare
prose — so a judge that required the whole completion to be JSON would refuse
every real completion, and one that read numbers out of the surrounding text
would make the measurement depend on the model's formatting. Locating an object
that parses is neither.

A completion that did not stop cleanly MUST be refused before it is parsed.
JSON truncated at a token limit can still parse as a smaller valid object, and a
judgement missing two dimensions that scores on the rest is a wrong number that
reads like a right one.

#### Scenario: Deliberation before the scores
- **WHEN** the completion contains the model's reasoning followed by a JSON object
- **THEN** the object is read and the reasoning is ignored, with no delimiter required

#### Scenario: A fenced block
- **WHEN** the completion wraps the object in a code fence
- **THEN** the object is read

#### Scenario: Prose with no object
- **WHEN** the completion contains scores written as text and no JSON object
- **THEN** the judgement is refused, because reading numbers from prose makes the measurement depend on formatting

#### Scenario: A truncated completion
- **WHEN** the completion did not stop cleanly
- **THEN** the judgement is refused before parsing, even if what arrived would parse

#### Scenario: Two objects
- **WHEN** the completion contains more than one top-level object
- **THEN** the last one is the judgement, because a model that restates its answer puts the final form last

#### Scenario: A refused judgement still cost tokens
- **WHEN** a judgement is refused
- **THEN** the model call is already recorded, because the provider layer records before the judge reads
