## Why

Settings live in three TOML files and **nine** environment variables — one more
than anyone thought, because `SECOND_SHIFT_PRICING` is a bare string literal in
`pricing.py` with no constant and no documentation. There is no single place to
look, and adding voice and brain location would have made it eleven.

An adversarial review of the existing surface found the sprawl is not the
problem. The problem is that every reader invented its own rules:

- **Empty string means two different things.** Six settings use `or`, so
  `VAR=` falls back to the default. `SECOND_SHIFT_DB` uses `.get(name, default)`,
  so `VAR=` is an empty path and crashes at import. `Environment=VAR=` is the
  ordinary way to clear a line in a systemd unit.
- **A malformed file is indistinguishable from a missing one.** Both
  `config.py` and `location.py` catch a TOML parse error and return empty. A
  one-character typo in `models.toml` makes `local-only` unavailable with the
  reason *"no expected local model is configured"* — naming the wrong cause, in
  a message the capture UI shows the user.
- **Failure timing is four different policies nobody chose.** Pricing raises at
  startup, profile raises at startup, brain raises at use, location and models
  degrade silently. Consolidation will unify these by accident unless the
  classification is written down first.
- **An unrecognized `SECOND_SHIFT_SYNTHETIC` silently means "real."** A typo in
  the judge deployment's unit produces real-flagged rows in the demo instance,
  permanently, in append-only tables.
- **`resolve_profile(env=...)` is only half-injectable.** It takes an env
  mapping but `local_endpoint()` and `expected_local_model()` read `os.environ`
  directly, so any "print resolved configuration" built on that parameter would
  print values the system does not use.
- **The fallback port contradicts the documented policy.** `config.py` defaults
  to 8000; `models.toml` sets 8200 and its own comment reserves 8000 as the port
  an ad-hoc server will grab. An unreadable config aims the probe at exactly the
  port the project reserved against.

## What Changes

**One surface.** A configuration module that owns every setting: its name, its
type, its default, its source file, whether it is secret, and when it fails.
Precedence is stated once — environment overrides file overrides default — and
empty string means "unset" everywhere, without exception.

**Failure timing becomes a declared property**, not an accident of which module
happened to catch which exception:

| Setting | Timing | Why |
|---|---|---|
| Deployment identity, profile, pricing | refuse to start | A wrong value corrupts measurements that cannot be backfilled |
| Brain location | fail at use | An unavailable brain must never take down capture |
| Location, voice | degrade | A rendering detail must not block a text feature |

**Malformed is not missing.** A parse error is a distinct, named finding that
says which file and which line. A missing file is a default.

**Voice becomes a setting with nothing behind it.** TTS is unverified and which
voices exist on this hardware is unknown until the week-3 spike. An unset or
unusable voice degrades to text and never raises at any layer — text-first is a
constitution principle, and a briefing that will not render because a voice is
missing would violate it. The default lives in TOML rather than Python, because
a docstring naming a TTS model would fail the source scan that keeps model
identifiers inside `providers/`.

**Brain location becomes a first-class setting** rather than a module constant.

**Deployment identity reaches the client.** `is_synthetic` currently reaches
every database row but no response, so the judge deployment cannot label itself
as a demo — which principle 5 requires and which cannot be paid for with a
`DEMO_MODE` branch.

**`config show`** prints resolved values with the source of each, redacts
anything declared secret, and states which process's environment it resolved
under — because the API unit and the sync unit do not set the same variables,
so a value printed from a shell is not necessarily the value anything uses.

## Capabilities

### New Capabilities
- `configuration`: settings as a declared, single surface — resolution,
  precedence, failure timing, and inspection.

### Modified Capabilities
- `compute-profiles`: the probe's endpoint and expected model come from the
  configuration surface, and profile resolution becomes fully injectable so a
  resolved view reflects what the system actually uses.

## Constitution Compliance

| Principle | Status | Note |
|---|---|---|
| 2. Privacy Airlock | **Strengthens** | The spec states that policy enforcement and redaction are *not* configurable, before a general settings surface exists to invite a flag. "A redaction step that is skippable by configuration" is the principle's own named violation. |
| 4. Text-First | **Protects** | Voice is explicitly exempt from startup validation. Without that, adding the setting would make a text briefing fail on an unverified speech stack. |
| 5. One codebase, two deployments | **Implements** | Deployment identity becomes declared, validated and visible to the client, so the judge instance can label itself without a branch. |
| 7. Telemetry from line one | **Strengthens** | An unparseable deployment identity refuses to start instead of silently meaning "real". Today a typo permanently contaminates append-only measurement tables. |

No violations.

## Decisions taken without a marker

- **Empty string is unset, everywhere.** One rule, no exceptions, because
  `Environment=VAR=` is ordinary in a unit file and currently crashes one
  setting and is ignored by six.
- **A parse error names the file and the failure.** It is never silently a
  default, and never reported as an absent value.
- **The voice default lives in TOML.** A Python docstring naming a TTS model
  would fail `test_no_model_identifier_outside_providers` from inside a comment.
- **`config show` redacts by declaration, not by name-matching.** A value is
  secret because it was declared secret; guessing from a name is how a
  differently-named credential gets printed.
- **Home coordinates are treated as personal** and redacted by default in
  `config show`, so pasting output into a document, an issue, or a report cannot
  publish them.
- **Deprecation is reported through the recorder or a startup line, never
  `warnings.warn`.** The test configuration sets `filterwarnings = ["error"]`,
  so a deprecation warning would fail every test that exercises a legacy name.

## Impact

**New:** `secondshift/config/` — declarations, resolution, inspection.
`config/voice.toml`.

**Changed:** `config.py`, `pricing.py`, `api/location.py`, `brain/repo.py`,
`api/main.py` all read through the surface instead of `os.environ`.
`CapabilityResponse` gains the deployment label.

**Deployment risk, and it is the real one.** The systemd units on the Spark are
hand-installed copies; `deploy.sh` never touches `/etc/systemd/system` or
`~/.config/systemd`. Shipping renamed variables without re-installing the units
silently drops the database path and the brain path to defaults — against a live
deployment currently holding real captured ideas. This is why migration is an
open question rather than a detail.

Also: `deploy.sh` does `rm -rf` on the deployed tree every time, so any writable
configuration living inside it is destroyed on the next deploy and silently
reverts to the tracked default.

## Open Questions

[NEEDS CLARIFICATION: How are the existing environment variable names migrated? Keeping every old name working as an alias is safest for the running deployment but leaves nine legacy names documented forever, which is most of the sprawl this change exists to remove. Renaming cleanly requires re-installing the systemd units on the Spark by hand — `deploy.sh` does not touch them — and getting that wrong silently repoints the database and brain to defaults while real captures are arriving. A third option is aliases now with a removal date recorded in the roadmap.]

[NEEDS CLARIFICATION: Is there a secrets layer, and where does it sit in precedence? `.gitignore` already reserves `.env`, `.env.local` and `.env.*.local`, so one was anticipated; `Recorder.descriptor_for` already takes a credential; and the next capability in the queue needs Nebius credentials. If `.env` is loaded, does it outrank the process environment or yield to it? A `.env` that outranks `Environment=` in a unit file can repoint the running deployment's database from a file nobody remembers editing.]

[NEEDS CLARIFICATION: Is configuration a startup snapshot or re-read at use? Today it is both by accident — `home_location()` re-reads TOML on every capture, while pricing is loaded once, so editing `pricing.toml` to fix a missing rate has no effect until the API restarts and nothing says so. A snapshot is predictable and makes `config show` truthful; re-reading lets a rate be added without dropping captures during a restart. Whichever is chosen, the other files' headers need to say which they are.]
