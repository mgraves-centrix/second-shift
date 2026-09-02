# Configuration prompt

> **✅ Shipped 2 Sep — `openspec/changes/archive/2026-09-02-add-configuration`.**
> Kept as the record of what was asked. Two things below did not survive contact
> with the code, and both are worth reading before writing the next prompt:
>
> 1. **The open decision was the wrong question.** It asks whether an
>    unresolvable required value is a startup or a runtime failure. Enumerating
>    all thirteen says the axis is **absent versus malformed** — absent is
>    legitimate for twelve of them, malformed for none.
> 2. **"What good looks like" says a malformed file should be loud, and loud
>    turned out not to mean raising.** `api/app.py` resolves the profile at
>    construction, so raising on a malformed `models.toml` takes capture down
>    over a file capture never reads. It reports through the capability finding
>    and a non-zero exit instead.

Paste as the first message of a fresh session. Entirely local — no Spark, no
tailnet, no credentials.

---

Build `configuration`. Read `openspec/constitution.md`, `CLAUDE.md`, and
`docs/SPEC_ROADMAP.md` first; they are the rules, not background.

## Why this one, and why first

Thirteen `SECOND_SHIFT_*` variables are read across three TOML files, and there
is no way to ask the system what it resolved or where a value came from. Every
capability after this adds more — this prompt said *ten* when it was written on
2 Sep and `retrieval` had already added three the same day, which is the argument
for the enumeration test below in one sentence. Sequence it first or it never
gets cheaper.

It is also the only thing that makes the always-on machine debuggable. When the
capability probe says `local_reasoner unavailable` on a box you are reaching over
a tailnet, the question is always *which host and port did it actually try* — and
today the only way to answer is to read the code and re-derive the precedence.

## What already exists — do not invent any of it

These are read from the environment, verified by scanning the source on 2 Sep:

```
SECOND_SHIFT_BRAIN            SECOND_SHIFT_LOCAL_HOST    SECOND_SHIFT_PRICING
SECOND_SHIFT_DB               SECOND_SHIFT_LOCAL_MODEL   SECOND_SHIFT_PROFILE
SECOND_SHIFT_EMBEDDER_HOST    SECOND_SHIFT_LOCAL_PORT    SECOND_SHIFT_RUBRIC_OVERWRITE
SECOND_SHIFT_EMBEDDER_MODEL   SECOND_SHIFT_LOCATION      SECOND_SHIFT_SYNTHETIC
SECOND_SHIFT_EMBEDDER_PORT
```

Do not trust that block either — regenerate it. It was ten names until the drift
pass on 2 Sep found the three `EMBEDDER_*` ones `retrieval` had added:

```bash
grep -rho 'SECOND_SHIFT_[A-Z_]*' --include='*.py' --include='*.sh' \
  apps/api/secondshift deploy scripts | sort -u
```

Three TOML files: `config/models.toml`, `config/pricing.toml`,
`config/location.toml`. Plus `config/evals/rubric.md` and `candidates.md`, which
are content rather than settings and are **not** yours to touch.

`secondshift/config.py` already resolves the local reasoner
(`local_reasoner_settings()`), the endpoint, the served-model name and the
profile. `api/location.py` and `telemetry/pricing.py` each load their own TOML.
The precedence those already implement is environment, then file, then a default,
and that is settled — do not change it.

`SECOND_SHIFT_RUBRIC_OVERWRITE` is read by `deploy/spark/deploy.sh`, not by
Python. A resolved view that only covers Python is a view with a hole in it.

## The open decision

**Is an unresolvable required value a startup failure or a runtime one?**

Today they differ. A missing pricing rate raises `MissingRate` mid-run — loud,
but after the model call it was meant to price. A missing served-model name makes
the probe report the reasoner unavailable, which degrades the profile silently
and correctly. A missing database path defaults.

**Do not decide this by preference.** Decide it by enumerating, in the proposal,
every setting the system reads and what currently happens when it is absent or
malformed. Where the current behavior is already right, say so and keep it. The
answer is likely to be different per setting, and a uniform rule imposed over the
top would make three of them worse.

## What good looks like

- `python -m secondshift.config show` prints every setting: its name, its
  resolved value, and **where that value came from** — environment, which file,
  or a default. Not just the value.
- A value that came from a file names the file. A reader on the Spark should be
  able to fix a wrong setting without opening a single `.py`.
- It runs with no database, no brain and no network. Configuration resolution
  that needs the thing it configures is not diagnosis, it is a second failure.
- A secret-shaped value is redacted rather than printed. Nothing here is a
  credential today, and that will not stay true once `nebius-executor` lands.
- Exit code says something: zero when everything required resolved, non-zero when
  something required did not.

## Scope — what NOT to build

- **No new configuration format**, no YAML, no `.env` loader, no library.
- **No hot reload.** Settings resolve at startup. A process that changes
  behavior without restarting is one whose telemetry cannot be attributed.
- **No remote or layered config service.**
- **Do not move the model identifiers out of `config/models.toml`.** They are
  there because principle 5 forbids them in Python outside `providers/`.
- Nothing here writes to the database.

## Constitution hooks

- **Principle 5** governs. The source scan in `test_providers.py` asserts no
  model identifier appears in a `.py` outside `providers/`. A resolved view that
  hardcodes a default model name to print breaks it. Read the identifier, never
  embed it.
- **Principle 7** is not implicated: resolving configuration is neither an agent
  invocation nor a model call, so it opens no telemetry row. Do not add one.

## The loop

```bash
git status --short && openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q          # 358 pass today
npm --prefix apps/web run test && npm --prefix apps/web run typecheck
scripts/check-no-environment.sh && scripts/check-american-english.sh
```

All green before starting. Then propose, clarify, apply, verify, sync, archive —
`openspec validate <change> --strict` at each boundary. Commit the proposal
before writing code.

## Verification — one test makes this capability un-rottable

**Write the test that enumerates.** Scan the source tree for
`SECOND_SHIFT_[A-Z_]+`, and assert the resolved view knows about every one it
finds. Then adding a variable without adding it to the view fails the suite, and
this capability cannot silently decay the way it decayed into existence.

That test must be able to fail. Prove it: add a throwaway variable read in a
module, watch the suite go red, remove it.

Also:

- Precedence is exercised, not assumed: environment beats file beats default, for
  at least one setting, with all three cases asserted.
- A malformed TOML is reported with the file named, not swallowed into a default.
- Running with an empty environment and no config files does not crash.
- `bash -n` on any shell you touch.

## Quality bar

The code is the submission. Judges read this repository.

**Never ship:** a `TODO`; a function returning a plausible constant; a test that
passes with the implementation deleted; a broad `except` that exists to make a
test green; a second copy of the precedence logic that can drift from
`config.py`; a printed value the reader cannot trace to a source.

**Always:** match the surrounding idiom; prefer the boring construction; name a
non-obvious trade-off in a comment; let failures be loud. American English. No
hostnames, addresses, usernames or home paths in tracked files.

## Hard stops

Stop, record the question with your recommendation, and move on:

- A `[NEEDS CLARIFICATION]` marker. Do not answer your own.
- A constitution violation. Blocking, not advisory.
- Anything in `NOT_BUILDING.md`.
- Credentials, payment, account settings, or anything outward-facing.
- Rewriting published history or force-pushing.

## Report

1. The table you built to answer the open decision — every setting, what happens
   when it is absent, and whether you changed that.
2. What shipped, with test counts.
3. The output of `config show` on this machine, pasted.
4. Anything blocked, with your recommendation.
5. What you would do next, and why that rather than the alternative.
