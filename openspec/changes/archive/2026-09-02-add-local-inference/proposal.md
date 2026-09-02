## Why

Nothing in this system can reason. The registry binds `EchoReasoner` on every
profile, so a `local-only` idea today returns its own last message and records a
model call that no model made.

Spike B verified a vLLM server on the Spark and settled its configuration. A
verified server is not an implemented `Reasoner` — the interface has existed
since day 1 with no backend behind it, and everything downstream waits on one.
Eval scoring in particular cannot start: `score` needs something to generate
outputs, and `evals` shipped deliberately without it.

The base class already owns telemetry, the airlock already guards the call, and
the pricing table already carries `local-vllm` at zero. What is missing is one
`_do_complete` and the wiring that binds it.

## What Changes

**A `Reasoner` over the vLLM OpenAI-compatible endpoint**, implementing
`_do_complete` and nothing else. `urllib` and `json`, no SDK: the probe in
`config.py` already speaks to this server that way, and a client library for
four fields of one endpoint would add a dependency to do what the standard
library does.

**Bound in the registry on local profiles.** Endpoint and served-model name come
from `config/models.toml`, which is already where they live for the probe. On
`cloud` the placeholder stays, because that binding is `nebius-executor`.

**A systemd unit for the server itself.** Spike B left it running with
`--restart no` and no unit, so it does not survive a reboot — and dogfooding is
"every idea, no exceptions," which is the same argument that gave the API a unit.
The unit publishes the container's port 8000 on host **8200**, which is what
`config/models.toml` allocates and what the probe checks; the spike ran on 8000,
the port it also records as contested.

**Failures are recorded.** `Reasoner.complete` records telemetry *after*
`_do_complete` returns, so until now a model that timed out or refused left no
row at all — a gap precisely where the failure ledger earns its place. Every
provider's public method now records a failure that escapes its backend and
re-raises. The taxonomy already classifies these correctly: a timeout is
`model_timeout`, a refused connection is `network`, and a 500 whose body says
"out of memory" is `oom`.

**A truncated completion is visible.** `RawCompletion` carries the server's
`finish_reason`, and a completion that stopped for any reason other than `stop`
records a warning event. A brief cut off at the token limit and presented as
finished is a wrong answer that looks like a right one.

**Sampling is configuration.** `max_tokens`, `temperature` and the request
timeout live in `config/models.toml` beside the endpoint, not in Python.

Not in this change: the cloud reasoner, escalation to Super or Ultra, batch
submission, ASR, or embedding. Each has its own capability.

## Capabilities

### New Capabilities
- `local-inference`: text completion from the local vLLM server, behind the
  existing `Reasoner` interface, with the server supervised so it survives a
  reboot.

### Modified Capabilities
- `telemetry`: a failure escaping a provider backend is recorded rather than
  lost, and a completion that did not stop cleanly is visible.

## Constitution Compliance

| Principle | Status | Note |
|---|---|---|
| 1. Brain plaintext under git | Not applicable | This change reads no memory and writes none. |
| 2. Privacy Airlock | **Implements** | `provider_kind = "local-vllm"`, which `REMOTE_PROVIDERS` excludes and the `model_calls` CHECK permits under `local-only`. The endpoint is a configured host and port; nothing here can reach a remote provider, and `assert_permitted` still runs on every call. This is the first backend that makes `local-only` a real capability rather than an available-but-unbacked one. |
| 3. No empty mornings | Compliant | A reasoner failure raises to its caller and is recorded; it commits no partial output and holds nothing back. Stage checkpointing is the night pipeline's, and this does not constrain it. |
| 4. Text-first | Compliant | Text completion only. No speech dependency is introduced, and nothing here is on a voice path. |
| 5. One codebase, two deployments | **Implements** | The backend lives entirely in `providers/`, reached only through `Reasoner`. Binding is by resolved profile, with no demo branch. The model identifier stays in `config/models.toml`; the source scan that forbids one outside `providers/` still passes. |
| 6. Scope boundary | Compliant | Nothing in `NOT_BUILDING.md`. The completion path is what "artifact out" needs; no chat surface is added. |
| 7. Telemetry from line one | **Implements** | The base class records every call, and this change closes the failure gap it left. Instrumentation is not deferred: the failure path lands with the backend that can exercise it. |

No violations.

## Decisions taken without a marker

- **The provider never discards model output.** Spike B recorded that the served
  model emits visible chain-of-thought — every reply opening "Here's a thinking
  process:". Where vLLM's reasoning parser separates it, the structured
  `reasoning_content` and `reasoning_tokens` are read and reported as reasoning.
  Where it does not, the text is returned whole. No marker-string splitter: a
  heuristic that guesses where reasoning ends would silently delete the answer
  whenever it guessed wrong, and telemetry would then count tokens the caller
  never saw. Separating reasoning from answer for display is the brief
  renderer's decision, made on text it can still see.
- **`reasoning_tokens` are subtracted from `completion_tokens`.** The recorder
  sums prompt, completion and reasoning into `total_tokens`, so the three must be
  disjoint. OpenAI-compatible `usage` nests reasoning inside completion, and
  passing both through unchanged would inflate every local call.
- **`effort` is recorded but does not change the request.** The escalation policy
  in `docs/MODELS.md` is explicit that `local-only` never escalates, and the local
  profile serves exactly one model. Varying sampling by effort would invent a
  policy nobody decided.
- **Sampling lives in the config file, not in new environment variables.** Nine
  `SECOND_SHIFT_*` variables across three TOML files already have no single place
  to look; the `configuration` capability exists to fix that. Adding three more
  would make the problem it addresses worse.
- **Temperature is non-zero.** `evals` requires repeated sampling to report a
  spread rather than a point estimate, and a deterministic reasoner would make
  every sample identical — reporting a spread of zero that measures the sampler
  rather than the system.
- **The registry binds the real reasoner on any local profile.** A profile only
  resolves to `spark` or `workstation` when the probe has confirmed an endpoint
  serving the expected model by name. Falling back to an echo when that endpoint
  is missing is what produced a system that could not reason while appearing to.

## Impact

**New:** `secondshift/providers/vllm.py`. `deploy/spark/second-shift-reasoner.service`
and its user variant.

**Changed:** `providers/registry.py` binds it on local profiles.
`providers/base.py` records failures escaping a backend and flags a completion
that did not stop cleanly. `config.py` gains the reasoner's settings beside the
endpoint it already reads. `config/models.toml` gains sampling and timeout.

**Changed tests:** the two that call `Registry.bind("spark")` — including the
day-1 gate proving a local-only idea costs nothing — now run against a stub HTTP
server rather than an echo. The gate gets stronger: it proves the wiring through
a real request and response, which is what it always claimed to prove.

**Risk:** the server itself cannot be exercised from this window, so the unit is
verified by reading and syntax alone, and the provider is verified against a stub
that speaks the endpoint's documented shape. A stub agrees with the server on
everything except what the server actually does — the first real call on the
Spark is where the remaining risk sits, and the probe already refuses a server
holding the wrong model.
