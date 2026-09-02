# Add `configuration` — a resolved view with provenance

## Scale classification

**L2 — Feature.** One component (`secondshift/config.py` plus a new
`__main__`), no new dependency, no schema change, no cross-system coordination.
Under a day. Proposal plus tasks; no design doc, because the one decision this
change makes is argued below rather than deferred to a separate file.

## Why

Thirteen `SECOND_SHIFT_*` variables are read across three TOML files and one
shell script, and there is no way to ask the system what it resolved or where a
value came from. Every capability after this adds more: the count was **ten**
when `docs/prompts/CONFIGURATION.md` was written on 2 Sep, and `retrieval` had
already added three the same day without anyone noticing. That is the argument
for this capability and for its enumeration test in one sentence.

The concrete failure it fixes is on the always-on machine. When the probe
reports `local_reasoner unavailable` over a tailnet, the question is always
*which host and port did it actually try* — and today the only way to answer is
to read `config.py` and re-derive the precedence by hand.

## What already exists

Precedence is implemented and settled: **environment, then file, then a
default.** `config.py` resolves the profile, the local reasoner and the
embedder; `api/location.py` and `telemetry/pricing.py` each load their own TOML.
None of that changes here.

`SECOND_SHIFT_RUBRIC_OVERWRITE` is read by `deploy/spark/deploy.sh`, not by
Python. A resolved view that only covers Python is a view with a hole in it, so
it is included and labeled as shell-read.

## The open decision, answered by enumeration

**Is an unresolvable required value a startup failure or a runtime one?**

Every row below was **measured**, not read off the source — a script set each
state and recorded what came back.

| Setting | Read by | Absent → | Malformed → |
|---|---|---|---|
| `SECOND_SHIFT_PROFILE` | `config.resolve_profile` | probe, then `cloud` | ✅ `ValueError` naming the valid set |
| `SECOND_SHIFT_LOCAL_HOST` | `config.local_endpoint` | file, then `127.0.0.1` | n/a — any string is a host |
| `SECOND_SHIFT_LOCAL_PORT` | `config.local_endpoint` | file, then `8000` | ✅ `ValueError` from `int()` |
| `SECOND_SHIFT_LOCAL_MODEL` | `config.expected_local_model` | file, then `""` → probe reports the reasoner unverifiable | n/a |
| `SECOND_SHIFT_EMBEDDER_HOST` | `config.local_embedder_settings` | file, then `127.0.0.1` | n/a |
| `SECOND_SHIFT_EMBEDDER_PORT` | `config.local_embedder_settings` | file, then `8201` | ✅ `ValueError` from `int()` |
| `SECOND_SHIFT_EMBEDDER_MODEL` | `config.expected_embedder_model` | file, then `""` → registry raises `LocalEmbedderNotConfigured` | n/a |
| `SECOND_SHIFT_DB` | `api/main`, `brain/__main__`, `evals/__main__` | `~/second-shift-data/second-shift.db` | n/a |
| `SECOND_SHIFT_BRAIN` | `brain.repo.brain_path` | sibling `../second-shift-brain` | n/a — `BrainUnavailable` at use |
| `SECOND_SHIFT_LOCATION` | `api.location.home_location` | `config/location.toml`, then no coordinates | ❌ **swallowed** — identical to absent |
| `SECOND_SHIFT_PRICING` | `telemetry.pricing.PricingTable.load` | `config/pricing.toml`; missing file → `MissingRate` naming the path | ⚠️ bare `TOMLDecodeError`, **file not named** |
| `SECOND_SHIFT_SYNTHETIC` | `api/main` | `False` | anything outside `{1,true,yes}` → `False`, silently |
| `SECOND_SHIFT_RUBRIC_OVERWRITE` | `deploy/spark/deploy.sh` | deploy refuses on rubric mismatch | any non-empty value means set |

And the load sites behind them, also measured:

```
malformed models.toml -> _local_config(): {}
malformed models.toml -> local_endpoint(): ('127.0.0.1', 8000)
missing   models.toml -> local_endpoint(): ('127.0.0.1', 8000)
```

**The answer: the axis is not startup-versus-runtime. It is absent-versus-malformed.**

- **Absent is a legitimate deployment state for twelve of the thirteen**, and the
  current defaults are right. A missing `models.toml` genuinely means "use the
  defaults"; a missing `location.toml` genuinely means "no celestial layer." Not
  one of these becomes a startup failure. Imposing a uniform rule would have made
  ten settings worse, exactly as the prompt predicted.
- **Malformed is never legitimate.** Somebody wrote a value and the system threw
  it away. Three sites do that today, and the worst is the one the "why" section
  above describes: an operator edits `config/models.toml`, mistypes the TOML,
  redeploys, and the probe says `local_reasoner unavailable` — while the real
  cause is a syntax error nothing reports. A malformed file is indistinguishable
  from an absent one.

So the rule is: **a file that exists and cannot be parsed is loud and names
itself; a file that is absent is a default.** That changes three call sites, not
thirteen.

`SECOND_SHIFT_SYNTHETIC` is the one row that is neither. `is_synthetic` is a
constitution-load-bearing flag (principle 7), and `SECOND_SHIFT_SYNTHETIC=ture`
silently meaning "real data" is the wrong direction to fail. It is made strict:
an unrecognized value raises, naming what it accepts.

## What ships

- `python -m secondshift.config show` — every setting, its resolved value, and
  **where the value came from**: `environment`, a named file, or `default`.
- A `Setting` record and a single `resolve_all()` that walks the same functions
  the runtime uses. No second copy of the precedence logic.
- Provenance is derived by asking the existing resolvers, not by reimplementing
  them: the environment is checked, then the file is parsed for the key, then
  the default is what is left.
- Secret-shaped names (`*_KEY`, `*_TOKEN`, `*_SECRET`, `*_PASSWORD`) are
  redacted. Nothing here is a credential today; `nebius-executor` changes that.
- Exit code 0 when everything required resolved, 1 when it did not.
- Three loud-on-malformed fixes: `_local_config`, `_embedder_config`,
  `home_location`. `PricingTable.load` gets the file named in its parse error.
- An enumeration test that scans the tree for `SECOND_SHIFT_[A-Z_]+` and fails
  when the view does not know one.

## Constitution compliance

| Principle | Outcome | Why |
|---|---|---|
| 1. Brain plaintext under git | **Not implicated** | Reads no brain content. `SECOND_SHIFT_BRAIN`'s *path* is displayed; nothing is opened. |
| 2. Privacy Airlock | **Constrains** | The view runs with no network and reaches no provider. Redaction is the airlock's habit applied to the operator's terminal: a value that looks like a credential is not printed just because a diagnostic asked for it. |
| 3. No empty mornings | **Not implicated** | No night stage, no briefing. |
| 4. Text-first | **Not implicated** | No speech path. |
| 5. One codebase, two deployments | **Constrains, and is the point** | The judge instance and the personal instance differ *only* by these settings, so a view that explains them is what makes that claim checkable. No `if DEMO_MODE`. **The trap:** printing a default model identifier would put a model name in a `.py` outside `providers/`, which `test_providers.py`'s source scan fails the build on. Identifiers are read from `config/models.toml`, never embedded. |
| 6. Scope boundary | **Compliant** | Nothing in `NOT_BUILDING.md` — checked against both tables, not asserted. Not a config format, not a config service, not hot reload. |
| 7. Telemetry from line one | **Not implicated, deliberately** | Resolving configuration is neither an agent invocation nor a model call, so it opens no row and must not. Adding one would put a write in the one command that has to work when the database does not. `SECOND_SHIFT_SYNTHETIC` becoming strict *serves* this principle: it is the switch that keeps seed data out of measurements. |

No violations.

## Non-goals

- No new configuration format, `.env` loader, or library.
- No hot reload. Settings resolve at startup; a process that changes behavior
  without restarting is one whose telemetry cannot be attributed.
- No remote or layered config service.
- No move of model identifiers out of `config/models.toml`.
- No database write, and no database read.
- Per-role `max_tokens` — the roadmap parks it here, and it is **deferred**: it
  needs an `[agents]` block shape that `night-pipeline` will constrain, and
  guessing at it now buys nothing this capability needs. Recorded rather than
  dropped, in tasks.
