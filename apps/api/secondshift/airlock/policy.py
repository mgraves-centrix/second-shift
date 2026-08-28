"""Policy vocabulary and the call-time airlock guard.

The database `CHECK` on `model_calls` is the last line of defense: it makes a
privacy breach unrecordable. This module is the first — it refuses the call
before it is made, so a `local-only` idea never reaches the network at all
rather than being caught on the way into the database afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Policy(StrEnum):
    LOCAL_ONLY = "local-only"
    CLOUD_ASSISTED = "cloud-assisted"


class PolicySource(StrEnum):
    ENTRY_DEFAULT = "entry-default"
    DECISION_UPGRADE = "decision-upgrade"
    PROFILE_FORCED = "profile-forced"


class Provider(StrEnum):
    LOCAL_VLLM = "local-vllm"
    TOKEN_FACTORY = "token-factory"
    NEBIUS_JOB = "nebius-job"
    OTHER = "other"


#: Providers that transmit off the machine. Kept in one place so the guard, the
#: database constraint and the capability report cannot drift apart.
REMOTE_PROVIDERS: frozenset[str] = frozenset(
    {Provider.TOKEN_FACTORY, Provider.NEBIUS_JOB}
)


class AirlockViolation(PermissionError):
    """A local-only operation attempted to reach a remote provider."""


def is_remote(provider: str) -> bool:
    return provider in REMOTE_PROVIDERS


def assert_permitted(policy: str, provider: str) -> None:
    """Refuse a remote call made under local-only policy.

    Raised before the request leaves the process. The matching database
    constraint means that even a caller that bypasses this cannot record the
    result.
    """
    if policy == Policy.LOCAL_ONLY and is_remote(provider):
        raise AirlockViolation(
            f"policy {policy!r} forbids provider {provider!r}: a local-only idea "
            "may not reach a remote provider"
        )


# -- policy resolution -----------------------------------------------------


@dataclass(frozen=True, slots=True)
class PolicyResolution:
    """What a run may execute under, and why."""

    effective_policy: Policy
    policy_source: PolicySource
    permitted: bool
    cause: str | None = None


def resolve_policy(
    entry_default: str,
    *,
    available: bool,
    unavailable_reason: str | None = None,
    upgrade_decision_id: str | None = None,
) -> PolicyResolution:
    """Resolve the policy a run executes under.

    The entry default is the intent. A run may never be *widened* beyond it —
    local-only cannot become cloud-assisted — unless an explicit decision is
    attributable, in which case the source records that. Narrowing is always
    allowed; it can only increase the guarantee.

    Where the profile cannot honor the resulting policy, the resolution is not
    permitted. The caller quarantines rather than downgrading, because a silent
    downgrade is the exact failure the Privacy Airlock exists to prevent.
    """
    policy = Policy(entry_default)
    source = PolicySource.ENTRY_DEFAULT

    if policy is Policy.LOCAL_ONLY and upgrade_decision_id:
        policy = Policy.CLOUD_ASSISTED
        source = PolicySource.DECISION_UPGRADE

    if policy is Policy.LOCAL_ONLY and not available:
        return PolicyResolution(
            effective_policy=policy,
            policy_source=source,
            permitted=False,
            cause=unavailable_reason or "local-only is unavailable on this profile",
        )

    return PolicyResolution(
        effective_policy=policy, policy_source=source, permitted=True
    )
