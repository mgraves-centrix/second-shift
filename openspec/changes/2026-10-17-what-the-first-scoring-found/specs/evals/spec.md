# evals

## ADDED Requirements

### Requirement: A run is scored once

A run that holds any result MUST be refused for scoring before anything is
generated, naming the way out: record a new baseline and score that.

A run's samples are generated together under one judge. Scoring generates every
sample from scratch and results are unique per sample, so a second pass over a
run that already holds results cannot complete it — it can only fail partway or
mix two passes into one run.

A run with results whose judge was never recorded — the shape a process killed
partway leaves — SHALL be reported as interrupted, not as awaiting scoring,
because the second reads as an instruction to score it.

#### Scenario: A scored run is scored again
- **WHEN** scoring is requested for a run that already holds results
- **THEN** it is refused before any generation, and no result is added

#### Scenario: A run was interrupted
- **WHEN** a run holds results and its judge was never recorded
- **THEN** status reports it as interrupted and not scorable, and scoring it is refused

### Requirement: A refused judgement can be read back

A failure recorded for a sample SHALL name the model calls its text can be read
back from: the judge's completion that was refused, and the answer it was
judging, where each exists.

A recorded result SHALL reference the kept text of the answer it scored.

A refusal is a finding about the instrument, and on the first real checkpoint
three of them could be described only by the offset the parser died at.

#### Scenario: The judge wrote something unreadable
- **WHEN** a judgement is refused
- **THEN** the failure names the judge's call and the answer's, and both calls' text is kept

#### Scenario: A score points at what it scored
- **WHEN** a sample is scored
- **THEN** its result references the kept completion of the answer that was graded

## MODIFIED Requirements

### Requirement: The judge and rubric are pinned per run

An eval run SHALL record the judge model, its version, and the hash of the rubric
used. These MUST be recorded at the time of the run.

A model judge's recorded version SHALL include the hash of what it is asked and
the hash of how its answer is read, as well as the configured checkpoint. The
ask and the reader are the instrument: the same model asked differently, or
read differently, grades differently, and a version naming only the
checkpoint would let either change between two runs unseen.

#### Scenario: Pinning is recorded
- **WHEN** an eval run completes
- **THEN** the judge model, its version and the rubric hash are recorded against that run

#### Scenario: A changed rubric does not silently compare
- **WHEN** the rubric changes and a new run executes
- **THEN** the new run records a different rubric hash, so results under different rubrics are distinguishable rather than plotted together

#### Scenario: A changed ask is a changed version
- **WHEN** the text a model judge is asked changes
- **THEN** runs it scores afterwards record a different judge version

#### Scenario: A changed reader is a changed version
- **WHEN** the code that reads a judge's answer changes
- **THEN** runs it scores afterwards record a different judge version

### Requirement: Two runs are compared only when the comparison would mean something

There SHALL be a command that compares two recorded eval runs and reports the
difference in their scores.

It MUST refuse the comparison, rather than warn, when any of the following
holds, because each makes the reported number mean something other than what it
appears to mean:

- the two runs pin different rubrics;
- the two runs pin the same brain state, so nothing under test has changed;
- either run has no results at all, having been recorded but never scored;
- either run is incomplete, because a partial run is not comparable to a whole one;
- the two runs were graded by different judges;
- the two runs were graded by one judge at two versions, because one model
  asked two ways is two instruments as surely as two models are;
- either run is synthetic;
- the two runs were scored over different sets of prompts;
- either run does not record which model produced its outputs, because a guard
  that cannot see one side of the comparison is not a guard;
- the two runs' outputs were produced by different models, because then the
  difference is the model rather than the brain, and the brain is what the
  measurement is about.

Each condition SHALL be its own refusal with its own message. A reader of a
refusal is deciding what to do next, and "recorded but never scored" and
"scored but incomplete" call for different actions.

Every difference it reports SHALL be accompanied by the spread of both runs. A
difference smaller than the wider spread MUST NOT be presented as a change.

It SHALL report each rubric dimension separately as well as overall, because an
overall mean can be carried by one dimension moving while another regresses.

The unit of comparison SHALL be one prompt's mean rather than one sample, paired
across the two runs. Prompts differ from one another systematically, so an
estimate pooled over every sample mixes the variation between prompts into one
meant to describe the variation within them.

#### Scenario: The brain did not change
- **WHEN** both runs pin the same brain state
- **THEN** the comparison is refused and says so plainly, rather than reporting a number that measures sampling noise

#### Scenario: The rubric changed between the runs
- **WHEN** the two runs pin different rubrics
- **THEN** the comparison is refused, because a rubric is pinned to a measurement precisely so that this cannot be done silently

#### Scenario: The prompt set changed between the runs
- **WHEN** the two runs were scored over different prompts
- **THEN** the comparison is refused, because there is no pairing across two different sets and the alternative is comparing two different questions

#### Scenario: One run did not finish
- **WHEN** either run has a failed sample
- **THEN** the comparison is refused, because averaging over what survived hides which prompts did not

#### Scenario: A difference inside the noise
- **WHEN** the difference between the two means is smaller than the wider of the two spreads
- **THEN** it is reported as not shown to have moved, rather than as an improvement

#### Scenario: One dimension carries the mean
- **WHEN** the overall mean improves while a dimension regresses
- **THEN** both are visible, because the dimension is the finding and the mean is the headline

#### Scenario: A generated run is not evidence
- **WHEN** either run is synthetic
- **THEN** the comparison is refused and says which, rather than returning an empty report

#### Scenario: The model changed between the runs
- **WHEN** the two runs' outputs were produced by different models
- **THEN** the comparison is refused and names both models, because the difference it would report is the model and not the brain

#### Scenario: One run's generator is unrecorded
- **WHEN** either run has results that reference no model call
- **THEN** the comparison is refused, because the comparison cannot be shown to be between two states of one system rather than two systems

#### Scenario: The judge was asked differently between the runs
- **WHEN** the two runs were graded by the same judge model at different recorded versions
- **THEN** the comparison is refused and names both versions

### Requirement: A judgement is read from an object, never from prose around it

The judgement SHALL be the last JSON object in the completion that opens with
the key the judge was asked for, decoded as structured data from where it
begins. Where no object opens with that key, it SHALL be the last top-level JSON
object. Anything else MUST be refused as an unreadable judgement.

Nothing before the final object SHALL affect how it is read. On 17 Oct a
malformed draft earlier in a real completion left a forward scan reading the
rest of the text as the inside of a string, and the valid judgement after it
was refused.

If the final object does not decode, the judgement MUST be refused rather than
replaced by an earlier one: an earlier valid draft is a number the model talked
itself out of.

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
- **WHEN** the completion contains more than one object of the judgement's form
- **THEN** the last one is the judgement, because a model that restates its answer puts the final form last

#### Scenario: A malformed draft before the final judgement
- **WHEN** an earlier object in the completion is not valid JSON and the last one is
- **THEN** the last one is read, and nothing before it changes how

#### Scenario: A malformed final judgement
- **WHEN** the last object of the judgement's form does not decode
- **THEN** the judgement is refused, even if an earlier one would have decoded

#### Scenario: A refused judgement still cost tokens
- **WHEN** a judgement is refused
- **THEN** the model call is already recorded, because the provider layer records before the judge reads
