"""What the resolved profile can actually guarantee.

`local-only` is a hardware capability, not a preference. Where a profile cannot
honor it, the report says so with the specific probe finding that caused it —
"local reasoner endpoint 127.0.0.1:8000 unreachable", not "unavailable on this
profile". The reason is the whole point: a capture surface shows the option
disabled *with* that reason, which is what makes the privacy model legible
rather than theoretical.

Unavailable policies are always returned, marked. They are never omitted, so a
cloud deployment still shows that the Airlock exists.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import ENV_PROFILE, Profile, ProfileSource, ResolvedProfile
from .policy import Policy


@dataclass(frozen=True, slots=True)
class PolicyAvailability:
    policy: Policy
    available: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class CapabilityReport:
    profile: Profile
    degraded: bool
    policies: tuple[PolicyAvailability, ...]
    degradation_reason: str | None = None

    def for_policy(self, policy: str) -> PolicyAvailability:
        for availability in self.policies:
            if availability.policy == policy:
                return availability
        raise KeyError(f"unknown policy {policy!r}")

    def is_available(self, policy: str) -> bool:
        return self.for_policy(policy).available

    def reason_for(self, policy: str) -> str | None:
        return self.for_policy(policy).reason


def build_report(resolved: ResolvedProfile) -> CapabilityReport:
    """Derive what each policy can promise under this profile."""
    local_ok = resolved.probe.has_local_stack and resolved.profile is not Profile.CLOUD

    if local_ok:
        local_reason = None
    elif resolved.source is ProfileSource.ENVIRONMENT:
        local_reason = (
            f"profile pinned to {resolved.profile.value!r} by {ENV_PROFILE}; "
            "no local reasoner is bound on this profile"
        )
    else:
        local_reason = resolved.degradation_reason or "no local capability detected"

    return CapabilityReport(
        profile=resolved.profile,
        degraded=resolved.degraded,
        degradation_reason=resolved.degradation_reason,
        policies=(
            PolicyAvailability(Policy.LOCAL_ONLY, local_ok, local_reason),
            PolicyAvailability(Policy.CLOUD_ASSISTED, True, None),
        ),
    )
