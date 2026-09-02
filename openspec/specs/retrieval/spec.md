# retrieval Specification

## Purpose
Local embedding of the brain and captured entries, and brute-force cosine
search over them, producing bounded, attributable, policy-filtered context
that the rest of the system can safely assemble into a prompt — on every
compute profile, with nothing eligible for egress until it has been filtered.

## Requirements

### Requirement: Embedding runs locally on every compute profile

Text embedding SHALL execute locally regardless of the resolved compute
profile, including `cloud`. No configuration path SHALL route an embedding
call to a hosted embedding endpoint.

#### Scenario: Cloud profile still embeds locally
- **WHEN** the resolved profile is `cloud`
- **THEN** an embedding call still executes against the local embedder, and no remote embedding provider is constructed

#### Scenario: No remote embedder exists to select
- **WHEN** the provider registry is inspected for any profile
- **THEN** it contains no embedder implementation whose `provider_kind` names a remote provider

### Requirement: Context assembly filters by policy before returning

Assembled retrieval context SHALL be filtered by policy before it is returned
to a caller. A `local-only` entry's raw text MUST NOT appear anywhere in a
structure that assembly returns to a caller that could pass it to a remote
provider.

#### Scenario: Local-only entry excluded from egress-eligible context
- **WHEN** context is assembled for a prompt destined for a remote provider, and the corpus includes a `local-only` entry whose text is otherwise the best match
- **THEN** the assembled context contains no substring of that entry's raw text

#### Scenario: Local-only entry available to a local-only caller
- **WHEN** context is assembled for a prompt that will run entirely locally
- **THEN** `local-only` entries are eligible for inclusion

### Requirement: Assembled context is bounded and each piece is attributable

Context assembly SHALL return a bounded, ordered list of pieces. Each piece
MUST carry the score that ranked it, the source it was drawn from, and the
policy it carries.

#### Scenario: Result respects a caller-specified bound
- **WHEN** a caller requests assembly with a maximum number of pieces or a maximum size
- **THEN** the returned context does not exceed that bound

#### Scenario: Every piece names its score, source and policy
- **WHEN** assembly returns a non-empty context
- **THEN** each piece in it carries a score, a source identifier, and a policy value

### Requirement: The brain is read at a pinned commit when a run specifies one

Where a run pins a `brain_sha`, retrieval SHALL read brain content as of that
commit rather than the working tree. Where no commit is pinned, retrieval MAY
read the working tree.

#### Scenario: Two pinned commits return different content
- **WHEN** the same brain file differs between two commits, and retrieval reads it once pinned to each commit in turn
- **THEN** the two reads return the content each commit actually held

#### Scenario: A file absent at the pinned commit is empty, not an error
- **WHEN** retrieval reads a brain file at a pinned commit that predates the file's creation
- **THEN** the read returns empty content rather than raising

### Requirement: The index is derived and never a second source of truth

The embedding index SHALL be derivable in full from `entries` and the brain
at any time. No persisted store of vectors SHALL exist that could diverge
from those sources after a crash or an interrupted write.

#### Scenario: Rebuild after deletion is identical
- **WHEN** the index is discarded and rebuilt from the same `entries` and brain state
- **THEN** a subsequent search over it returns the same ranked results as before deletion

#### Scenario: No table or file holds vectors independently of a rebuild
- **WHEN** the database schema and the deployment's file layout are inspected
- **THEN** no table or file exists whose sole purpose is persisting embedding vectors between process restarts
