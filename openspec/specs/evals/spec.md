## Purpose

The measurement spine: a fixed prompt set run against a pinned judge and rubric,
sampled for variance, and attributed to the exact brain state that produced each
output.

## Requirements

### Requirement: A run is sampled, not measured once

Each active prompt SHALL be run several times within an eval run, and results
reported with a central value and a spread.

A single sample per prompt MUST NOT be presented as a measurement.

#### Scenario: Repeated sampling
- **WHEN** an eval run executes with three samples configured
- **THEN** each active prompt produces three recorded results, distinguished by sample index

#### Scenario: Variance is reportable
- **WHEN** results for a prompt are summarized
- **THEN** both a central value and a spread are available, so a difference between runs can be distinguished from sampling noise

### Requirement: The judge and rubric are pinned per run

An eval run SHALL record the judge model, its version, and the hash of the rubric
used. These MUST be recorded at the time of the run.

#### Scenario: Pinning is recorded
- **WHEN** an eval run completes
- **THEN** the judge model, its version and the rubric hash are recorded against that run

#### Scenario: A changed rubric does not silently compare
- **WHEN** the rubric changes and a new run executes
- **THEN** the new run records a different rubric hash, so results under different rubrics are distinguishable rather than plotted together

### Requirement: Scoring is attributed to a recorded brain state

An eval run SHALL record the brain commit it ran against. When scoring happens
separately from generation, it MUST be attributed to the brain commit recorded at
generation, never to the current one.

#### Scenario: Baseline inputs recorded before a judge exists
- **WHEN** a baseline is recorded while no model is available to score it
- **THEN** the prompts, the rubric hash and the brain commit are recorded, and the run is marked as awaiting scoring

#### Scenario: Later scoring uses the recorded state
- **WHEN** an awaiting-scoring run is scored days later, after the brain has changed
- **THEN** the results are attributed to the brain commit recorded at baseline, not to the brain's current commit

#### Scenario: Generation reads the brain at the recorded commit
- **WHEN** an awaiting-scoring run is generated and scored after the brain has changed
- **THEN** the brain content used is what that commit holds, not what the working tree currently holds — otherwise the pinning records a state the output was never produced from

#### Scenario: The recorded state is not overwritten by scoring
- **WHEN** scoring completes for a previously recorded run
- **THEN** the run's brain commit is unchanged

### Requirement: The judge is configured, not fixed in code

The scoring model SHALL be a configured value. The runner MUST work against any
judge satisfying the interface, and MUST be exercisable without a real model.

Scoring SHALL be reachable as a command, not only as a library call. A scoring
path that exists only where tests call it cannot produce the result the system is
built to report, and its absence is invisible from the command list.

The judge's pinned version SHALL be recorded from configuration rather than from
whatever the endpoint reports about itself, because a version read from the
server floats when the server is restarted against a different checkpoint.

#### Scenario: A stub judge exercises the runner
- **WHEN** the runner executes with a stub judge
- **THEN** results are produced and recorded exactly as with a real one

#### Scenario: No judge configured
- **WHEN** scoring is attempted with no judge configured
- **THEN** it fails clearly, naming what is missing, rather than recording unscored results as scored

#### Scenario: Scoring is reachable from the command line
- **WHEN** the operator lists the eval commands
- **THEN** scoring is among them, and running it against a recorded baseline generates and grades that run

#### Scenario: The pinned version is not the endpoint's word for itself
- **WHEN** a run is scored
- **THEN** the version recorded against it comes from configuration, so restarting the server against another checkpoint cannot change what a past run claims

### Requirement: Scores are structured, not parsed from prose

The judge SHALL return a score per rubric dimension as structured data. Scores
MUST NOT be extracted by parsing free text.

#### Scenario: Structured scores are recorded
- **WHEN** a judge scores an output
- **THEN** a value per rubric dimension is recorded, along with the total

#### Scenario: An unparseable judgement is a failure, not a zero
- **WHEN** a judge returns something that is not a valid set of scores
- **THEN** a typed failure is recorded and no score is written, because a zero would be indistinguishable from a genuinely poor answer

### Requirement: A partial run is recorded as partial

Where some samples succeed and others fail, the successful results SHALL be
recorded and the run marked incomplete.

#### Scenario: Some samples fail
- **WHEN** one sample of three fails while the others succeed
- **THEN** the two successful results are recorded, a typed failure is recorded for the third, and the run is identifiable as incomplete

#### Scenario: An incomplete run is not silently comparable
- **WHEN** an incomplete run is summarized
- **THEN** its incompleteness is evident, so it is not compared against a complete run as though equivalent

### Requirement: Prompts and rubric are content, loaded from files

Prompts and the rubric SHALL be loaded from files rather than embedded in code,
and prompts carry an active flag so a candidate set can be narrowed by selection
rather than deletion.

#### Scenario: Only active prompts run
- **WHEN** an eval run executes with some prompts marked inactive
- **THEN** only the active ones are run

#### Scenario: Selection does not lose the candidates
- **WHEN** prompts are narrowed to a chosen subset
- **THEN** the unselected candidates remain recorded rather than deleted

#### Scenario: The rubric hash follows its content
- **WHEN** the rubric file changes
- **THEN** the hash recorded by the next run differs

### Requirement: Scoring refuses a rubric that is not the one pinned

Scoring an eval run SHALL compare the hash of the rubric it was given against the
`rubric_sha` recorded on that run, before any output is generated. Where they
differ, scoring MUST fail, naming both hashes, and MUST record no results.

A rubric mismatch is not a failed sample. Every sample under a different rubric is
wrong in the same way, so it MUST NOT be recorded as a partial run.

#### Scenario: The rubric on disk is not the rubric pinned
- **WHEN** a run recorded under one rubric is scored with a different one
- **THEN** scoring fails before generating anything, names the run and both hashes, and writes no results and no partial run

#### Scenario: The rubric on disk is the rubric pinned
- **WHEN** a run is scored with the rubric whose hash it recorded
- **THEN** scoring proceeds and results are recorded as normal

#### Scenario: A mismatch is not recorded as a failed sample
- **WHEN** scoring is refused because the rubric does not match
- **THEN** no failure row is written for the individual samples, because the run did not partially succeed

### Requirement: The pinned rubric is reportable beside the file on disk

Status SHALL report every recorded eval run with its pinned rubric hash, its brain
commit, its week, and whether it is awaiting scoring — alongside the hash of the
rubric file currently on disk.

Where any recorded run's pinned rubric is not the file on disk, status MUST say so
explicitly and MUST exit non-zero. Reconciling a pinned hash MUST NOT require
reading the database by hand.

#### Scenario: Recorded runs and their pinning are reported
- **WHEN** status runs against a database holding an eval run
- **THEN** that run's id, week, pinned rubric hash, brain commit and awaiting-scoring state are printed, together with the hash of the rubric file on disk

#### Scenario: A run pinned to a different rubric is called out
- **WHEN** a recorded run's pinned rubric hash is not the hash of the rubric on disk
- **THEN** status states that the pinned rubric is not the file on disk, names both hashes, and exits non-zero

#### Scenario: Agreement is reported as agreement
- **WHEN** every recorded run pins the rubric currently on disk
- **THEN** status reports that they agree and exits zero

#### Scenario: No recorded runs
- **WHEN** status runs against a database with no eval runs
- **THEN** it reports the rubric on disk, states that no run has pinned it yet, and exits zero

### Requirement: Deployment does not silently replace a rubric that differs

Deployment SHALL compare the rubric on the target against the rubric being
shipped before replacing the target tree. Where they differ, deployment MUST stop
before anything is destroyed, name both hashes, and state how to retrieve the
target's copy.

Proceeding past a difference SHALL require an explicit override. An absent rubric
on the target is not a difference; an indeterminate one MUST NOT be treated as
absent.

#### Scenario: The target holds a rubric that differs
- **WHEN** deployment runs against a target whose rubric differs from the one being shipped
- **THEN** it stops before replacing the tree, prints both hashes, and names both the command that retrieves the target's copy and the override that would proceed anyway

#### Scenario: The target holds the same rubric
- **WHEN** the target's rubric is identical to the one being shipped
- **THEN** deployment proceeds without comment

#### Scenario: The target holds no rubric
- **WHEN** the target has no rubric file, as on a first deployment
- **THEN** deployment proceeds

#### Scenario: The override is explicit
- **WHEN** the operator sets the documented override and the rubrics differ
- **THEN** deployment proceeds, having stated that it is replacing a differing rubric

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

### Requirement: What would falsify the claim is fixed before the result exists

The difference that counts as an improvement SHALL be recorded before the second
run is scored, in a file whose content is hashed.

The comparison SHALL report that hash alongside its verdict, so that a threshold
edited after the result is visible wherever the result is read.

A comparison that does not meet the recorded bar SHALL be reported as no
improvement having been shown, which is not the same statement as the claim
having been disproved, and the distinction MUST be preserved in what is
reported.

Where the bar is met in the opposite direction, that SHALL be reported with the
same prominence as the favorable result.

#### Scenario: The threshold predates the number
- **WHEN** a reader asks whether the bar was chosen after seeing the result
- **THEN** the date it was fixed and the hash of the text are both in the comparison's own output, and the file's addition is in the history

#### Scenario: The bar is not met
- **WHEN** the difference does not clear the recorded bar
- **THEN** it is reported as no improvement shown, rather than as the brain having learned nothing

#### Scenario: The result goes the other way
- **WHEN** the bar is met in the direction of a regression
- **THEN** it is reported as a regression rather than withheld

#### Scenario: The threshold is edited afterwards
- **WHEN** the recorded text changes
- **THEN** the hash printed beside the verdict changes with it

### Requirement: A score records the model call that produced what was scored

Every recorded result SHALL reference the model call whose output the judge
graded. The generator is not inferable afterwards: two runs over the same
prompts, the same rubric and the same brain state are distinguishable only by
what produced their text, and a score with no reference to its call is a number
whose subject is unknown.

The callable that produces an output SHALL return the recorded call, not its
text alone. A callable returning text alone MUST be refused, naming the
parameter, rather than coerced — coercing it would restore the unrecorded case
without saying so, which is the state this requirement exists to end.

A run's distinct generating models SHALL be reportable from its summary, so the
question "what produced this run" is answerable without writing SQL against a
database on another machine.

#### Scenario: The call is recorded beside the score
- **WHEN** a sample is generated and graded
- **THEN** the recorded result references the model call that produced the output

#### Scenario: A generator that returns only text
- **WHEN** the callable returns a string rather than a recorded completion
- **THEN** scoring is refused, naming the parameter, rather than recording a result whose generator is unknown

#### Scenario: A run's generators are reportable
- **WHEN** a scored run is summarized
- **THEN** the distinct models behind its results are part of the summary

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

### Requirement: An eval answer is produced the way the product produces work

Generation for an eval run SHALL go through the agent invocation path, with the
eval prompt as the task and the brain at the run's pinned commit as the context,
rather than through a composition that exists only for evaluation.

The claim under measurement is that the system gets better at its job. An answer
produced by a harness prompt measures that harness, and an improvement in it
cannot be attributed to the product without a further argument nobody has made.

The agent turn SHALL carry the model call it recorded, so the result row can
name it. A turn whose call cannot be named forces its caller to choose between
an unattributed score and a second lookup that guesses.

#### Scenario: Generation goes through an agent
- **WHEN** an eval run is scored
- **THEN** each answer is produced by an agent invocation against the brain at the run's pinned commit, and the invocation is recorded

#### Scenario: The turn names its model call
- **WHEN** an agent turn completes
- **THEN** the model call it recorded is reachable from the turn, without a second lookup

### Requirement: A prompt edited between two runs is not a brain improvement

The comparison MUST refuse when the two runs' outputs were produced by different
agent prompts. A role prompt is versioned and content-hashed, and a prompt
replaced between week 1 and week 8 moves the scores for a reason that has
nothing to do with memory.

Absence on both sides SHALL compare equal, because generating without an agent
is a legitimate shape; what is refused is a change between the runs rather than
an absence in them.

This SHALL read the prompt through the recorded call rather than from a new
column: a result names its model call, the call names its invocation, the
invocation names its agent, and the agent carries the prompt hash.

#### Scenario: The role prompt changed between the runs
- **WHEN** the two runs' outputs were produced by different agent prompt versions
- **THEN** the comparison is refused and names both, because the difference it would report is the prompt and not the brain

#### Scenario: Neither run used an agent
- **WHEN** neither run's results name an agent invocation
- **THEN** the comparison proceeds, because an absence shared by both sides is not a change between them
