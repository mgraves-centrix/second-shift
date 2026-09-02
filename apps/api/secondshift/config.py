"""Compute profile resolution.

The Spark is a capability tier, not a requirement. Resolution order is the
`SECOND_SHIFT_PROFILE` environment variable, then a capability probe, then
`cloud` as the default — and the resolved profile plus the probe's findings are
stamped onto every run and model call, so any row can be explained afterwards.

The probe reports a SET of findings rather than a boolean. A partial stack —
CUDA present but the inference endpoint unreachable — has to be visible as
exactly that, because the reason `local-only` is unavailable must name the
finding that caused it rather than a generic profile message.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import socket
import tomllib
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

ENV_PROFILE = "SECOND_SHIFT_PROFILE"
ENV_LOCAL_MODEL = "SECOND_SHIFT_LOCAL_MODEL"
ENV_LOCAL_HOST = "SECOND_SHIFT_LOCAL_HOST"
ENV_LOCAL_PORT = "SECOND_SHIFT_LOCAL_PORT"
ENV_EMBEDDER_MODEL = "SECOND_SHIFT_EMBEDDER_MODEL"
ENV_EMBEDDER_HOST = "SECOND_SHIFT_EMBEDDER_HOST"
ENV_EMBEDDER_PORT = "SECOND_SHIFT_EMBEDDER_PORT"
ENV_DB = "SECOND_SHIFT_DB"
ENV_BRAIN = "SECOND_SHIFT_BRAIN"
ENV_LOCATION = "SECOND_SHIFT_LOCATION"
ENV_PRICING = "SECOND_SHIFT_PRICING"
ENV_SYNTHETIC = "SECOND_SHIFT_SYNTHETIC"
ENV_RUBRIC_OVERWRITE = "SECOND_SHIFT_RUBRIC_OVERWRITE"
ENV_ARTIFACTS = "SECOND_SHIFT_ARTIFACTS"
#: Not a `SECOND_SHIFT_*` name — Tavily's own convention, and the CLI reads it
#: too. Registered here anyway: a resolved view that omits a credential the
#: system depends on is a view with a hole where the important part goes.
ENV_TAVILY_KEY = "TAVILY_API_KEY"

_MODELS_CONFIG = Path(__file__).resolve().parents[3] / "config" / "models.toml"

CUDA = "cuda"
LOCAL_REASONER = "local_reasoner"
SPEECH_STACK = "speech_stack"


class Profile(StrEnum):
    SPARK = "spark"
    WORKSTATION = "workstation"
    CLOUD = "cloud"


class ProfileSource(StrEnum):
    ENVIRONMENT = "environment"
    PROBE = "probe"
    DEFAULT = "default"


@dataclass(frozen=True, slots=True)
class Capability:
    name: str
    available: bool
    detail: str

    def __str__(self) -> str:
        return f"{self.name}: {'available' if self.available else self.detail}"


@dataclass(frozen=True, slots=True)
class ProbeResult:
    capabilities: dict[str, Capability] = field(default_factory=dict)

    def available(self, name: str) -> bool:
        capability = self.capabilities.get(name)
        return bool(capability and capability.available)

    def detail(self, name: str) -> str:
        capability = self.capabilities.get(name)
        return capability.detail if capability else f"{name}: not probed"

    def missing(self) -> list[Capability]:
        return [c for c in self.capabilities.values() if not c.available]

    @property
    def has_local_stack(self) -> bool:
        """A local reasoner needs both the accelerator and a reachable endpoint."""
        return self.available(CUDA) and self.available(LOCAL_REASONER)

    @property
    def is_partial(self) -> bool:
        """Some local capability present, but not enough to serve locally."""
        return bool(self.capabilities) and not self.has_local_stack and any(
            c.available for c in self.capabilities.values()
        )


@dataclass(frozen=True, slots=True)
class ResolvedProfile:
    profile: Profile
    source: ProfileSource
    probe: ProbeResult
    degraded: bool = False
    degradation_reason: str | None = None


# -- individual checks -----------------------------------------------------


def _check_cuda() -> Capability:
    """Detected without importing a framework: no torch outside providers/."""
    if shutil.which("nvidia-smi"):
        return Capability(CUDA, True, "nvidia-smi present")
    return Capability(CUDA, False, "no CUDA device detected (nvidia-smi not found)")


#: Spellings `SECOND_SHIFT_SYNTHETIC` accepts. Strict on purpose, and the only
#: setting here that raises: `is_synthetic` is what keeps seed rows out of a
#: measurement (principle 7), and `SYNTHETIC=ture` silently meaning "this is
#: real data" fails in the direction that cannot be undone. Refusing to start is
#: recoverable; a contaminated eight-week curve is not.
_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"", "0", "false", "no", "off"})


class UnrecognizedFlagValue(ValueError):
    """A boolean-shaped setting was given a value that is neither true nor false."""


def synthetic_flag(env: dict[str, str] | None = None) -> bool:
    """Whether this deployment marks the rows it writes as synthetic."""
    raw = (os.environ if env is None else env).get(ENV_SYNTHETIC, "")
    lowered = raw.strip().lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise UnrecognizedFlagValue(
        f"{ENV_SYNTHETIC}={raw!r} is neither true nor false. Accepted: "
        f"{sorted(_TRUE)} or {sorted(v for v in _FALSE if v)}, or leave it "
        "unset. Refusing to guess, because guessing false would write seed "
        "rows that no measurement can later tell apart from real ones."
    )


class MalformedConfigFile(RuntimeError):
    """A configuration file exists and could not be parsed.

    Carried rather than raised at most call sites. See `models_config_error`.
    """


def _read_toml(path: Path) -> tuple[dict, str | None]:
    """Parse a TOML file into `(data, error)`.

    An absent file is `({}, None)` — a legitimate deployment state meaning
    "use the defaults." A present but unparseable one is `({}, message)`, and
    the message names the file.

    The two used to be indistinguishable, which is the defect this capability
    exists to end: an operator mistypes `config/models.toml`, redeploys, and the
    probe reports the reasoner *unreachable* while the real cause is a syntax
    error nothing mentions. The error is returned rather than raised because
    `api/app.py` resolves the profile at construction, so raising here would
    take down capture over a file capture never reads.
    """
    try:
        return tomllib.loads(path.read_text()), None
    except OSError:
        return {}, None
    except tomllib.TOMLDecodeError as exc:
        return {}, f"{path} is malformed: {exc}"


def models_config_error() -> str | None:
    """The parse failure in the models config, if it has one.

    The probe reads this so a malformed file surfaces as the reason a capability
    is unavailable, rather than as a default that looks deliberate.
    """
    return _read_toml(_MODELS_CONFIG)[1]


def _local_config() -> dict:
    """The `[local]` block from the models config, or empty if unreadable.

    Empty on a malformed file too — see `models_config_error` for how the
    operator finds out, and `_read_toml` for why this does not raise.
    """
    return _read_toml(_MODELS_CONFIG)[0].get("local", {})


def local_endpoint() -> tuple[str, int]:
    """Where the local reasoner is expected to listen.

    Read from configuration rather than defaulted, because the port is a
    deployment choice: 8000 is the vLLM default and therefore the port an
    unrelated server will grab, which is exactly the collision the probe should
    not have to arbitrate.
    """
    local = _local_config()
    env_port = os.environ.get(ENV_LOCAL_PORT)
    return (
        os.environ.get(ENV_LOCAL_HOST) or local.get("reasoner_host", "127.0.0.1"),
        int(env_port) if env_port else int(local.get("reasoner_port", 8000)),
    )


@dataclass(frozen=True, slots=True)
class LocalReasonerSettings:
    """Everything needed to talk to the local inference server.

    One value rather than five lookups, because the probe and the provider must
    agree about which endpoint they mean. They disagreed once already: the spike
    served on 8000 while this file allocated 8200.
    """

    host: str
    port: int
    model: str
    max_tokens: int
    temperature: float
    timeout_s: float

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


def local_reasoner_settings() -> LocalReasonerSettings:
    """Endpoint, served-model name and sampling, from configuration.

    Sampling is here rather than in the providers package for the same reason
    the rubric is a file: changing how the model is sampled is not a code
    change, and a value baked into Python is one nobody can adjust on the
    machine that runs it.
    """
    local = _local_config()
    host, port = local_endpoint()
    return LocalReasonerSettings(
        host=host,
        port=port,
        model=expected_local_model(),
        max_tokens=int(local.get("reasoner_max_tokens", 4096)),
        temperature=float(local.get("reasoner_temperature", 0.7)),
        timeout_s=float(local.get("reasoner_timeout_s", 300)),
    )


def _embedder_config() -> dict:
    """The `[embedder]` block from the models config, or empty if unreadable."""
    return _read_toml(_MODELS_CONFIG)[0].get("embedder", {})


@dataclass(frozen=True, slots=True)
class LocalEmbedderSettings:
    """Everything needed to talk to the local embedding server.

    `dimensions` is configuration rather than something read from the first
    response: the index allocates its array up front, and a server swapped for
    a model of a different width should fail as a shape mismatch naming both
    numbers rather than silently building an index nothing can search.
    """

    host: str
    port: int
    model: str
    dimensions: int
    timeout_s: float

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


def local_embedder_settings() -> LocalEmbedderSettings:
    """Endpoint, served-model name and width, from configuration.

    An absent `[embedder]` block yields an empty model name rather than raising.
    The registry is what refuses to bind on that, for the same reason
    `local_reasoner_settings` leaves the refusal to its caller: reading
    configuration and deciding what a missing value means are different jobs.
    """
    embedder = _embedder_config()
    env_port = os.environ.get(ENV_EMBEDDER_PORT)
    return LocalEmbedderSettings(
        host=os.environ.get(ENV_EMBEDDER_HOST)
        or embedder.get("embedder_host", "127.0.0.1"),
        port=int(env_port) if env_port else int(embedder.get("embedder_port", 8201)),
        model=expected_embedder_model(),
        dimensions=int(embedder.get("embedder_dimensions", 2048)),
        timeout_s=float(embedder.get("embedder_timeout_s", 30)),
    )


def expected_embedder_model() -> str:
    """The identifier the local embedding server must report for itself.

    Kept out of Python for the same reason as the reasoner's: no model
    identifier may appear outside the providers package, and a source scan in
    the test suite fails the build when one does.
    """
    override = os.environ.get(ENV_EMBEDDER_MODEL)
    if override:
        return override
    return _embedder_config().get("embedder_model", "")


def expected_local_model() -> str:
    """The identifier the local reasoner must report for itself.

    Configuration rather than a constant: for vLLM this is whatever
    `--served-model-name` was chosen at launch, so the probe cannot know it
    otherwise. Kept out of Python because no model identifier may appear outside
    the providers package.
    """
    override = os.environ.get(ENV_LOCAL_MODEL)
    if override:
        return override
    return _local_config().get("reasoner_model", "")


def _served_models(host: str, port: int, timeout: float) -> list[str] | None:
    """Identifiers a reachable endpoint reports for itself, or None if it cannot say."""
    url = f"http://{host}:{port}/v1/models"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return None
    return [m.get("id", "") for m in data if isinstance(m, dict)]


def _check_endpoint(
    host: str,
    port: int,
    expected_model: str | None = None,
    timeout: float = 0.25,
    identity_timeout: float = 2.0,
) -> Capability:
    """Is a local reasoner serving the model we expect?

    Reachability alone is not evidence. An endpoint on this port may be any
    process at all — on 2026-08-27 it was a vLLM server holding a different
    model entirely, which the previous reachability-only check reported as an
    available local reasoner. A local-only idea would then have been routed to
    an unverified model, and telemetry would have recorded the identifier the
    caller intended rather than the one that answered.
    """
    malformed = models_config_error()
    if malformed:
        return Capability(
            LOCAL_REASONER,
            False,
            f"cannot determine the local reasoner: {malformed}. The host and "
            f"port below are built-in defaults, not what that file says.",
        )

    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError as exc:
        return Capability(
            LOCAL_REASONER,
            False,
            f"local reasoner endpoint {host}:{port} unreachable ({exc.__class__.__name__})",
        )

    expected = expected_model if expected_model is not None else expected_local_model()
    served = _served_models(host, port, identity_timeout)

    if served is None:
        return Capability(
            LOCAL_REASONER,
            False,
            f"endpoint {host}:{port} accepts connections but does not identify "
            "the model it serves",
        )
    if not expected:
        return Capability(
            LOCAL_REASONER,
            False,
            f"endpoint {host}:{port} serves {served!r} but no expected local "
            "model is configured, so it cannot be verified",
        )
    if expected in served:
        return Capability(
            LOCAL_REASONER, True, f"serving {expected!r} at {host}:{port}"
        )
    return Capability(
        LOCAL_REASONER,
        False,
        f"endpoint {host}:{port} serves {served!r}, not the expected "
        f"{expected!r} — refusing to treat it as the local reasoner",
    )


def _check_speech(module: str) -> Capability:
    try:
        found = importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        found = False
    if found:
        return Capability(SPEECH_STACK, True, f"{module} importable")
    return Capability(SPEECH_STACK, False, f"speech stack {module!r} not importable")


def probe(
    *,
    reasoner_host: str | None = None,
    reasoner_port: int | None = None,
    expected_model: str | None = None,
    speech_module: str = "nemo",
    checks: dict[str, Callable[[], Capability]] | None = None,
) -> ProbeResult:
    """Run every capability check independently."""
    configured_host, configured_port = local_endpoint()
    host = reasoner_host if reasoner_host is not None else configured_host
    port = reasoner_port if reasoner_port is not None else configured_port
    runners: dict[str, Callable[[], Capability]] = checks or {
        CUDA: _check_cuda,
        LOCAL_REASONER: lambda: _check_endpoint(host, port, expected_model),
        SPEECH_STACK: lambda: _check_speech(speech_module),
    }
    return ProbeResult({name: run() for name, run in runners.items()})


# -- resolution ------------------------------------------------------------


def resolve_profile(
    *,
    env: dict[str, str] | None = None,
    probe_result: ProbeResult | None = None,
) -> ResolvedProfile:
    """Resolve the profile, degrading rather than aborting on a partial stack.

    A partial local stack degrades to `cloud` and startup proceeds. It does not
    abort, and it does not silently pretend the local capability exists: the
    findings that caused the degradation are carried on the result and become
    the reason `local-only` is reported unavailable.
    """
    environment = os.environ if env is None else env
    override = environment.get(ENV_PROFILE)
    result = probe_result if probe_result is not None else probe()

    if override:
        try:
            chosen = Profile(override)
        except ValueError as exc:
            raise ValueError(
                f"{ENV_PROFILE}={override!r} is not one of "
                f"{[p.value for p in Profile]}"
            ) from exc
        return ResolvedProfile(
            profile=chosen, source=ProfileSource.ENVIRONMENT, probe=result
        )

    if result.has_local_stack:
        profile = (
            Profile.SPARK if result.available(SPEECH_STACK) else Profile.WORKSTATION
        )
        return ResolvedProfile(profile=profile, source=ProfileSource.PROBE, probe=result)

    reason = "; ".join(c.detail for c in result.missing()) or "no local capability"
    return ResolvedProfile(
        profile=Profile.CLOUD,
        source=ProfileSource.PROBE if result.capabilities else ProfileSource.DEFAULT,
        probe=result,
        degraded=result.is_partial,
        degradation_reason=reason,
    )


# -- the resolved view -----------------------------------------------------
#
# Thirteen variables are read across three TOML files and one shell script, and
# until this existed there was no way to ask what resolved or where it came
# from. The count was ten when `docs/prompts/CONFIGURATION.md` was written on
# 2 Sep and `retrieval` had already added three the same day — which is why
# `test_configuration.py` scans the tree rather than trusting this list.
#
# Nothing here re-implements precedence. Each setting resolves by calling the
# same function the runtime calls, so a second copy cannot drift from the first.


class Origin(StrEnum):
    ENVIRONMENT = "environment"
    FILE = "file"
    DEFAULT = "default"


REDACTED = "<redacted>"

#: Name suffixes that mark a value as a credential. Nothing here is one today;
#: `nebius-executor` changes that, and a diagnostic that prints a key the first
#: time somebody runs it on a shared screen is a diagnostic nobody runs twice.
_SECRET_SUFFIXES = ("_KEY", "_TOKEN", "_SECRET", "_PASSWORD")


@dataclass(frozen=True, slots=True)
class Setting:
    """One environment variable, and what is known about it without reading it."""

    name: str
    read_by: str
    describes: str
    #: False for settings every deployment can legitimately leave unset.
    required: bool = False
    #: True where only shell reads it, so a Python-only view would have a hole.
    shell_only: bool = False

    @property
    def secret(self) -> bool:
        return self.name.endswith(_SECRET_SUFFIXES)


@dataclass(frozen=True, slots=True)
class Resolved:
    """What a setting resolved to, and where the value came from."""

    setting: Setting
    value: str
    origin: Origin
    #: The file a `FILE` origin came from, or the file that would have supplied
    #: it. Named so a wrong value can be corrected without opening a `.py`.
    source_path: Path | None = None
    #: Set when the file exists and could not be parsed.
    error: str | None = None

    @property
    def display(self) -> str:
        if self.setting.secret and self.value:
            return REDACTED
        return self.value

    @property
    def where(self) -> str:
        if self.error:
            return f"{self.source_path} (MALFORMED)"
        if self.origin is Origin.FILE and self.source_path:
            return str(self.source_path)
        return str(self.origin)


SETTINGS: tuple[Setting, ...] = (
    Setting(ENV_PROFILE, "config.resolve_profile", "compute profile override"),
    Setting(ENV_LOCAL_HOST, "config.local_endpoint", "local reasoner host"),
    Setting(ENV_LOCAL_PORT, "config.local_endpoint", "local reasoner port"),
    Setting(
        ENV_LOCAL_MODEL,
        "config.expected_local_model",
        "served-model name the local reasoner must report",
    ),
    Setting(ENV_EMBEDDER_HOST, "config.local_embedder_settings", "local embedder host"),
    Setting(ENV_EMBEDDER_PORT, "config.local_embedder_settings", "local embedder port"),
    Setting(
        ENV_EMBEDDER_MODEL,
        "config.expected_embedder_model",
        "served-model name the local embedder must report",
    ),
    Setting(ENV_DB, "api.main, brain, evals", "SQLite database path", required=True),
    Setting(ENV_BRAIN, "brain.repo.brain_path", "brain repository path", required=True),
    Setting(ENV_LOCATION, "api.location.home_location", "home coordinates file"),
    Setting(ENV_PRICING, "telemetry.pricing", "rate table path", required=True),
    Setting(
        ENV_ARTIFACTS,
        "artifacts.store.artifact_root",
        "where produced artifacts land on disk",
        required=True,
    ),
    Setting(
        ENV_TAVILY_KEY,
        "providers.tavily.TavilyProvider",
        "search credential; absent means the research stage is skipped",
    ),
    Setting(ENV_SYNTHETIC, "api.main", "mark written rows as synthetic"),
    Setting(
        ENV_RUBRIC_OVERWRITE,
        "deploy/spark/deploy.sh",
        "allow a deploy to replace the target's rubric",
        shell_only=True,
    ),
)


def _origin_of(name: str, *, file_key: str | None, config: dict) -> Origin:
    """Which layer supplied this value, by the same order the resolvers use."""
    if os.environ.get(name):
        return Origin.ENVIRONMENT
    if file_key is not None and file_key in config:
        return Origin.FILE
    return Origin.DEFAULT


def resolve_all(env: dict[str, str] | None = None) -> list[Resolved]:
    """Every setting, its resolved value, and where that value came from.

    Runs with no database, no brain, no configuration file and no network:
    diagnosis that needs the thing being diagnosed is a second failure, not a
    diagnosis. Nothing here opens a connection or writes a telemetry row —
    resolving configuration is neither an agent invocation nor a model call.
    """
    from .api.location import location_config_error, location_path
    from .artifacts.store import default_root as default_artifact_root
    from .brain.repo import brain_path
    from .telemetry.pricing import default_pricing_path

    environment = os.environ if env is None else env
    local = _local_config()
    embedder = _embedder_config()
    models_error = models_config_error()
    location_error = location_config_error()

    def models(name: str, key: str, value: object) -> Resolved:
        config = local if key.startswith("reasoner") else embedder
        return Resolved(
            setting=by_name(name),
            value=str(value),
            origin=_origin_of(name, file_key=key, config=config),
            source_path=_MODELS_CONFIG,
            error=models_error,
        )

    reasoner = local_reasoner_settings()
    embed = local_embedder_settings()

    profile_set = environment.get(ENV_PROFILE, "")
    rows = [
        Resolved(
            setting=by_name(ENV_PROFILE),
            value=profile_set or "(resolved by probe at startup)",
            origin=Origin.ENVIRONMENT if profile_set else Origin.DEFAULT,
        ),
        models(ENV_LOCAL_HOST, "reasoner_host", reasoner.host),
        models(ENV_LOCAL_PORT, "reasoner_port", reasoner.port),
        models(ENV_LOCAL_MODEL, "reasoner_model", reasoner.model),
        models(ENV_EMBEDDER_HOST, "embedder_host", embed.host),
        models(ENV_EMBEDDER_PORT, "embedder_port", embed.port),
        models(ENV_EMBEDDER_MODEL, "embedder_model", embed.model),
        _path_setting(ENV_DB, environment, _default_db_path()),
        _path_setting(ENV_BRAIN, environment, brain_path()),
        Resolved(
            setting=by_name(ENV_LOCATION),
            value=str(location_path()),
            origin=Origin.ENVIRONMENT
            if environment.get(ENV_LOCATION)
            else Origin.DEFAULT,
            source_path=location_path(),
            error=location_error,
        ),
        _path_setting(ENV_PRICING, environment, default_pricing_path()),
        _path_setting(ENV_ARTIFACTS, environment, default_artifact_root()),
        Resolved(
            setting=by_name(ENV_TAVILY_KEY),
            value=environment.get(ENV_TAVILY_KEY, ""),
            origin=Origin.ENVIRONMENT
            if environment.get(ENV_TAVILY_KEY)
            else Origin.DEFAULT,
        ),
        _synthetic_row(environment),
        Resolved(
            setting=by_name(ENV_RUBRIC_OVERWRITE),
            value="set" if environment.get(ENV_RUBRIC_OVERWRITE) else "unset",
            origin=Origin.ENVIRONMENT
            if environment.get(ENV_RUBRIC_OVERWRITE)
            else Origin.DEFAULT,
        ),
    ]
    return rows


def _synthetic_row(environment: dict[str, str]) -> Resolved:
    """The synthetic flag, reporting an unrecognized value rather than raising.

    `synthetic_flag()` raises by design — but the whole point of this view is to
    still answer when something is wrong, so here the refusal becomes a row the
    operator can read instead of a traceback that hides the other twelve.
    """
    raw = environment.get(ENV_SYNTHETIC, "")
    try:
        value = str(synthetic_flag(environment))
        error = None
    except UnrecognizedFlagValue as exc:
        value = raw
        error = str(exc)
    return Resolved(
        setting=by_name(ENV_SYNTHETIC),
        value=value,
        origin=Origin.ENVIRONMENT if raw else Origin.DEFAULT,
        error=error,
    )


def _default_db_path() -> Path:
    """Where the database lives when nothing says otherwise.

    Duplicated from `api/main.py` deliberately? No — imported from it would drag
    in FastAPI and the app graph, which this view must run without. The value is
    asserted equal in the test suite instead, so the two cannot drift silently.
    """
    return Path(os.path.expanduser("~/second-shift-data/second-shift.db"))


def _path_setting(name: str, environment: dict[str, str], default: Path) -> Resolved:
    override = environment.get(name)
    return Resolved(
        setting=by_name(name),
        value=str(override or default),
        origin=Origin.ENVIRONMENT if override else Origin.DEFAULT,
    )


def by_name(name: str) -> Setting:
    for setting in SETTINGS:
        if setting.name == name:
            return setting
    raise KeyError(f"{name} is not a registered setting")


if __name__ == "__main__":  # pragma: no cover - exercised via config_cli
    # `python -m secondshift.config show`. The parsing and printing live in
    # `config_cli` so that this module, which the whole system imports, stays
    # free of both.
    import sys

    from .config_cli import main

    sys.exit(main())
