"""Failure classification.

The ledger is queryable, not a text dump: every failure carries a type from a
fixed taxonomy and a normalized signature so recurrence can be derived by
grouping rather than by incrementing a counter.

An error that matches nothing is still recorded — classified to the closest
applicable type with its original message preserved. Dropping an unrecognized
failure would hide exactly the novel problems the ledger exists to surface.
"""

from __future__ import annotations

import hashlib
import re
from enum import StrEnum


class FailureType(StrEnum):
    DEPENDENCY_BUILD = "dependency_build"
    MODEL_TIMEOUT = "model_timeout"
    OOM = "oom"
    TOOL_QUOTA = "tool_quota"
    TOOL_ERROR = "tool_error"
    BAD_OUTPUT = "bad_output"
    ORCHESTRATOR_CRASH = "orchestrator_crash"
    NETWORK = "network"


class BadOutput(Exception):
    """Output was produced but rejected at critique."""


class ToolQuotaExceeded(Exception):
    """An external tool refused the call on quota grounds."""


# Ordered: the first pattern to match wins, so specific precedes general.
_PATTERNS: tuple[tuple[re.Pattern[str], FailureType], ...] = (
    (re.compile(r"\b(out of memory|oom|cuda.*memory)\b", re.I), FailureType.OOM),
    (re.compile(r"\b(timed?\s*out|timeout|deadline exceeded)\b", re.I), FailureType.MODEL_TIMEOUT),
    (re.compile(r"\b(quota|rate.?limit|429|credits? exhausted)\b", re.I), FailureType.TOOL_QUOTA),
    (re.compile(r"\b(dns|connection refused|unreachable|ssl|tls|socket)\b", re.I), FailureType.NETWORK),
    (re.compile(r"\b(wheel|build failed|no matching distribution|compil)\w*\b", re.I), FailureType.DEPENDENCY_BUILD),
)

_EXCEPTION_TYPES: tuple[tuple[type[BaseException], FailureType], ...] = (
    (BadOutput, FailureType.BAD_OUTPUT),
    (ToolQuotaExceeded, FailureType.TOOL_QUOTA),
    (MemoryError, FailureType.OOM),
    (TimeoutError, FailureType.MODEL_TIMEOUT),
    (ConnectionError, FailureType.NETWORK),
    (OSError, FailureType.NETWORK),
)

_VOLATILE = re.compile(
    r"0x[0-9a-f]+"           # addresses
    r"|\b\d{4}-\d{2}-\d{2}\b"  # dates
    r"|\d+\.\d+"               # floats and durations, including "12.5s"
    r"|\b\d{3,}\b"             # long numbers, ids, ports
    r"|'[^']{24,}'",           # embedded ULIDs and long literals
    re.I,
)


def classify(exc: BaseException) -> FailureType:
    """Map an exception to its taxonomy entry.

    Message patterns are checked before exception types: a `RuntimeError`
    saying "CUDA out of memory" is an OOM, not an orchestrator crash.
    """
    message = str(exc)
    for pattern, failure_type in _PATTERNS:
        if pattern.search(message):
            return failure_type
    for exc_type, failure_type in _EXCEPTION_TYPES:
        if isinstance(exc, exc_type):
            return failure_type
    return FailureType.ORCHESTRATOR_CRASH


def signature(failure_type: FailureType, exc: BaseException, *, scope: str = "") -> str:
    """A stable dedup key for the same failure recurring.

    Volatile detail — addresses, timestamps, ids, durations — is stripped so
    that two occurrences of one problem group together. The full message is
    stored separately and is never lost.
    """
    normalized = _VOLATILE.sub("*", str(exc)).strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)[:200]
    digest = hashlib.sha256(
        f"{failure_type}|{scope}|{type(exc).__name__}|{normalized}".encode()
    ).hexdigest()[:16]
    return f"{failure_type}:{scope or type(exc).__name__}:{digest}"
