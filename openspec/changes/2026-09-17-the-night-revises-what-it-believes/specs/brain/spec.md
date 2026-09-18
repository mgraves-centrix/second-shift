## ADDED Requirements

### Requirement: A night may revise what the brain believes

A night SHALL apply the beliefs its distillation proposed to the brain's topic
files, and SHALL commit them with that night's own record. A belief SHALL
replace an existing line only where it named exactly one; otherwise it SHALL be
appended. A night that proposes no belief SHALL leave the brain unchanged.

#### Scenario: A revised belief replaces the line it named
- **WHEN** a night proposes a belief naming exactly one line of a topic file
- **THEN** that line is replaced, and the change is committed with the night's record

#### Scenario: A line that cannot be identified is never overwritten
- **WHEN** a proposed belief names a line that is absent, or that appears more than once
- **THEN** the belief is appended and no existing line is changed

#### Scenario: A night that learned nothing changes nothing
- **WHEN** a night proposes no belief
- **THEN** no topic file is modified

#### Scenario: More beliefs than a night may propose are refused whole
- **WHEN** a distillation proposes more beliefs than the cap allows
- **THEN** none of them is applied
