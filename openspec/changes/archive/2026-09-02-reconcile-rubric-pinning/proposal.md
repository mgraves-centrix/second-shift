## Why

`python -m secondshift.evals status` on the always-on machine reports rubric
`4a7c2e91b3d0`. `config/evals/rubric.md` has exactly one version in the entire
git history, at `a4fb4da`, and it hashes to `b4decd6fe774`. No committed rubric
has ever hashed to what the machine read, so this is not a checkout sitting
behind — it is a copy of the file that git has never seen.

Three separate defects let that happen, and each of them is in this repository.

**Nothing prints the pinned hash.** `status` hashes the file on disk at the
moment it runs. The value that matters is `eval_runs.rubric_sha` on the baseline
row, and no command reports it. Answering "is the baseline sound?" today means
opening the database by hand with SQL written from memory, on a machine most
tooling cannot reach. A pinned value nobody can read is not pinned in any useful
sense.

**Nothing enforces the pinned hash.** `score` takes a `Rubric` loaded from disk
and never compares it against the `rubric_sha` the run recorded. Week 1 would be
graded against whatever rubric happens to be on disk on the day a judge finally
exists, and the resulting number would carry a `rubric_sha` that did not produce
it. That is the exact failure the pinning was introduced to exclude, and it fails
silently — a wrong number, not an error.

**Deployment destroys the evidence.** `deploy.sh` does `rm -rf` on the remote
tree and re-extracts. A rubric edited only on the machine — the most likely cause
of the mismatch, and the only remaining copy of whatever `4a7c2e91b3d0` is — is
deleted by the next deploy with nothing printed. The file needed to answer the
question is destroyed by the routine act of shipping.

The first defect is why the mismatch could not be diagnosed. The second is why it
would have become a wrong measurement rather than a stopped one. The third is why
it may not be diagnosable much longer.

## What Changes

**`status` reports every recorded run beside the file on disk.** Run id, week,
pinned `rubric_sha`, `brain_sha`, and whether the run is awaiting scoring — the
contents of the hand-written `SELECT` this reconciliation currently requires,
as a supported command. Where a run's pinned rubric is not the file on disk,
`status` says so in those words and exits non-zero, because a status command that
prints a fatal inconsistency and exits zero is how this went unnoticed for six
days.

**`score` refuses a rubric that is not the one pinned.** Before any generation,
the loaded rubric's hash is compared against the run's `rubric_sha`. A mismatch
raises, naming both hashes and the run, and writes nothing. Grading week 1
against a rubric week 1 never used produces a number that is worse than no
number, because it looks like evidence.

**`deploy.sh` refuses to overwrite a rubric that differs.** Before the `rm -rf`,
the remote rubric is hashed and compared against the one being shipped. If they
differ the deploy stops, prints both hashes, and gives the command that copies the
remote file off the machine. An operator who genuinely intends the overwrite says
so with `SECOND_SHIFT_RUBRIC_OVERWRITE=1`; nothing else proceeds past it.

Not in this change: reconciling the baseline row itself. That needs a value only
the always-on machine holds, and where it lands is a decision rather than an
implementation. See below.

## Capabilities

### Modified Capabilities
- `evals`: the pinned rubric hash becomes readable and enforced, rather than
  recorded and trusted.

## Constitution Compliance

| Principle | Status | Note |
|---|---|---|
| 1. Brain plaintext under git | Compliant | Untouched. The brain commit is read, never written, and this change does not alter how `brain_sha` is recorded or resolved. |
| 2. Privacy Airlock | Compliant | No new egress and no new provider call. The rubric is a fixed, authored document carrying no captured content; hashing it locally moves nothing. |
| 3. No empty mornings | Not applicable | Nothing here runs in the night pipeline. |
| 4. Text-first | Not applicable | No voice surface. |
| 5. One codebase, two deployments | Compliant | The guard is in the runner and the shared entry point, identical on both instances. No provider specifics, no demo-only path. |
| 6. Scope boundary | Compliant | Nothing in `NOT_BUILDING.md` is approached. This tightens an existing capability rather than adding one. |
| 7. Telemetry from line one | Compliant | Adds no agent invocation and no model call, so it opens no telemetry row and skips none. A refused score writes no `eval_results`, which is the point: a refusal is not a partial run and must not be recorded as one. |

No violations.

## Decisions taken without a marker

- **The guard lives in `score`, not in the entry point.** `__main__.py` has no
  `score` command yet, deliberately. Putting the check in the runner means the
  provider path that eventually calls it inherits the guard rather than having to
  remember it.
- **A mismatch raises rather than recording a failure.** The per-sample `except`
  in `score` converts errors into `failures` rows and continues. A wrong rubric
  is not a bad sample — every sample would be wrong — so the check runs before the
  loop, where nothing catches it.
- **`status` exits non-zero on drift.** It mixes reporting with asserting, which
  is usually worth avoiding. Here the quiet exit code is the defect: the drift was
  visible in `status` output for six days and read as normal.
- **The deploy guard covers the rubric only.** It is the one file in `config/`
  whose content hash is recorded in the database and whose drift silently
  invalidates a measurement. `candidates.md` is superseded by `eval_prompts.active`
  in the database, and the TOML files carry no pinned hash.
- **The override is an environment variable, not a flag.** `deploy.sh` takes its
  configuration from the environment already, and the override should read as
  deliberate configuration rather than something added to a habitual command line.

## Deliberately out of scope: whether to re-record the baseline

This change makes the reconciliation answerable and stops the drift doing damage.
It does not perform it, because the deciding value — `eval_runs.rubric_sha` on the
baseline row — exists only on the always-on machine.

- If the baseline pinned `b4decd6fe774`, the baseline is sound and the file
  drifted afterward. Restoring the committed rubric on the machine resolves it,
  and no baseline is re-recorded.
- If the baseline pinned `4a7c2e91b3d0`, week 1 is pinned to a rubric absent from
  a public repository whose entire argument is that the measurement is
  reproducible from it. Whether to re-record is a judgement about the measurement,
  not about the code, and belongs to the person being measured.

Either way, `status` after this change prints the value, and `score` will not run
until it agrees with the file.

## Impact

**Changed:** `secondshift/evals/runner.py` — a pre-flight check in `score` and a
typed error for it. `secondshift/evals/__main__.py` — `status` reports recorded
runs and their pinning. `deploy/spark/deploy.sh` — a pre-wipe rubric comparison.

**Unchanged:** the schema, the recorded baseline, `config/evals/rubric.md`. This
change reads the rubric and never writes it; the file's own opening line forbids
editing in place, and superseding it with `rubric-v2.md` is a decision this change
does not take.

**Risk:** the deploy guard runs against a host this window cannot reach, so it is
verified by syntax check and by reading rather than by execution. It fails closed:
the remote probe reports either a hash or the literal `absent`, and anything else —
including a probe that cannot run — aborts under `set -e` rather than falling
through to the wipe. A wrong guard therefore costs a deploy, never a rubric.
