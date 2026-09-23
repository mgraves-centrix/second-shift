# Refuse the push, rather than remembering to check

## Scale classification

**L1 — Small task.** One hook, one line of documentation, one test. Nothing
changes for anybody until they run a `git config` line, and nothing in the
product moves.

## Why

`docs/development/GATES.md` says "everything runs on every push". That is true
of CI and not of the push, and the gap is not hypothetical: **this session
pushed a red commit twice**, both times because the gate's exit status never
reached the shell.

```bash
python3 scripts/gate.py | tail -2 && git push     # the pipeline's status is tail's
python3 scripts/gate.py > log 2>&1; git push      # the semicolon discards it
```

Both read as careful. Neither is. The second happened after the first had been
written up, which is the argument: this is not a thing to remember harder.

CI catches it afterwards, so nothing stays broken — but what lands is a red
commit on a pushed branch, and `--no-ff` history keeps it.

## What changes

**`.githooks/pre-push`** runs `scripts/gate.py` and refuses the push on any
non-zero exit. Enabled per clone:

```bash
git config core.hooksPath .githooks
```

Tracked in the repository rather than left in `.git/hooks`, so it is reviewable
and arrives with a clone; opt-in by that one line, because a hook that installs
itself is a hook that surprises somebody.

**A deletion is not gated.** `git push --delete` sends an all-zero local hash
and has no tree to check; running a two-minute gate to remove a branch is the
kind of friction that gets a hook uninstalled.

**The refusal names `--no-verify`**, the same shape as every other refusal here:
`restore --overwrite`, `backup --same-device-ok`, `SECOND_SHIFT_RUBRIC_OVERWRITE`.
An override that is undocumented is one people discover by disabling the whole
mechanism.

## What this does not do

It does not make the gate faster, and it does not add a fast path for a
documentation-only change. `GATES.md` already argues that one: at this size it
would save under a minute and cost a second definition of passing.

## Impact

**Affected specs:** `test-harness` (one added requirement).

**Affected code:** `.githooks/pre-push` (new), `docs/development/GATES.md`.

## Constitution Compliance

| Principle | Bearing | How this change stands |
|---|---|---|
| 1. Brain plaintext under git | Not engaged | — |
| 2. The Privacy Airlock | Not engaged | Runs the existing gate; nothing leaves. |
| 3. No empty mornings | Not engaged | — |
| 4. Text-first, voice layered | Not engaged | — |
| 5. One codebase, two deployments | Not engaged | A development hook. Nothing ships it. |
| 6. Scope boundary | Respected | Not a product surface. |
| 7. Telemetry from line one | **Considered, deliberately not applied** | No model call, no invocation. The gate's own output is the record. |

No violation.

## Risk

**A two-minute wait on every push.** The cost, stated: measured at about 113
seconds. Accepted, because the thing it prevents happened twice in three days
and the alternative is a discipline that has already failed.

**A hook somebody disables.** Which is why the refusal names the override
instead of hiding it — `--no-verify` for one push is a decision; `git config
--unset core.hooksPath` because the message was unhelpful is an erosion.
