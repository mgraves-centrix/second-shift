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
import os
import shutil
import socket
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

ENV_PROFILE = "SECOND_SHIFT_PROFILE"

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


def _check_endpoint(host: str, port: int, timeout: float = 0.25) -> Capability:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return Capability(LOCAL_REASONER, True, f"reachable at {host}:{port}")
    except OSError as exc:
        return Capability(
            LOCAL_REASONER,
            False,
            f"local reasoner endpoint {host}:{port} unreachable ({exc.__class__.__name__})",
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
    reasoner_host: str = "127.0.0.1",
    reasoner_port: int = 8000,
    speech_module: str = "nemo",
    checks: dict[str, Callable[[], Capability]] | None = None,
) -> ProbeResult:
    """Run every capability check independently."""
    runners: dict[str, Callable[[], Capability]] = checks or {
        CUDA: _check_cuda,
        LOCAL_REASONER: lambda: _check_endpoint(reasoner_host, reasoner_port),
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
