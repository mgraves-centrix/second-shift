"""Reading what an out-of-process job says it did.

A job writes this beside what it produced, and the poller collects it. Nothing
in it is taken on faith: it arrived from someone else's machine, and every row it
produces lands in the accounting the cost curve and the local-versus-cloud
comparison are read from.

So the reading is strict in both directions. A field nobody maps is refused
rather than ignored, because the most likely such field is a cost the job
computed for itself, and the recorder computes cost from the rate table. A field
that is missing is refused rather than defaulted, because a model call with no
token count reads as free. A refusal leaves the whole report unrecorded and the
run visibly unaccounted for, which is the state that is true.
"""

from __future__ import annotations

import json
from typing import Any

from .recorder import ExternalInvocation, ExternalModelCall


class UnreadableReport(ValueError):
    """A job's telemetry that cannot be recorded as it stands."""


_INVOCATION_REQUIRED = {"local_id": str, "agent_id": str}
_INVOCATION_OPTIONAL = {
    "parent_local_id": str,
    "stage": str,
    "input_summary": str,
    "started_at_ms": int,
    "ended_at_ms": int,
    "outcome": str,
}
_CALL_REQUIRED = {
    "local_id": str,
    "parent_local_id": str,
    "provider": str,
    "model": str,
    "policy": str,
    "compute_profile": str,
    "prompt_tokens": int,
    "completion_tokens": int,
}
_CALL_OPTIONAL = {"total_tokens": int, "latency_ms": int, "ts_ms": int}


def parse_report(
    text: str, *, dispatcher: str
) -> tuple[list[ExternalInvocation], list[ExternalModelCall]]:
    """The invocations, parents first, and the model calls a report records.

    `dispatcher` is the invocation this job was dispatched under, as the poller
    knows it — never as the report says. A report naming another is refused:
    with no inbound channel, this is what authenticating a report means. The
    poller only reads output it asked a job for, and nothing in that output
    chooses where it attaches.
    """
    try:
        report = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise UnreadableReport(f"the job's telemetry is not JSON: {exc}") from exc
    if not isinstance(report, dict):
        raise UnreadableReport("the job's telemetry is not an object")

    _no_unmapped(report, {"dispatching_invocation_id", "invocations", "model_calls"}, "report")
    named = report.get("dispatching_invocation_id")
    if named != dispatcher:
        raise UnreadableReport(
            f"the report names dispatch {named!r}, and this job was dispatched "
            f"under {dispatcher!r}; it is not attached anywhere"
        )

    invocations = [
        ExternalInvocation(**_fields(item, _INVOCATION_REQUIRED, _INVOCATION_OPTIONAL, "invocation"))
        for item in _list(report, "invocations")
    ]
    calls = [
        ExternalModelCall(**_fields(item, _CALL_REQUIRED, _CALL_OPTIONAL, "model call"))
        for item in _list(report, "model_calls")
    ]
    ordered = _parents_first(invocations)
    known = {i.local_id for i in ordered}
    for call in calls:
        if call.parent_local_id not in known:
            raise UnreadableReport(
                f"model call {call.local_id!r} names invocation "
                f"{call.parent_local_id!r}, which the report does not contain"
            )
    return ordered, calls


def _list(report: dict, key: str) -> list:
    value = report.get(key, [])
    if not isinstance(value, list):
        raise UnreadableReport(f"{key} is {type(value).__name__}, not a list")
    return value


def _no_unmapped(item: dict, allowed: set[str], what: str) -> None:
    extra = sorted(set(item) - allowed)
    if extra:
        raise UnreadableReport(
            f"{what} carries {', '.join(extra)}, which nothing records; refusing "
            "rather than dropping it"
        )


def _fields(
    item: Any, required: dict[str, type], optional: dict[str, type], what: str
) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise UnreadableReport(f"a {what} is {type(item).__name__}, not an object")
    _no_unmapped(item, set(required) | set(optional), what)
    out: dict[str, Any] = {}
    for name, kind in required.items():
        if name not in item:
            raise UnreadableReport(f"a {what} has no {name}")
        out[name] = _typed(item[name], kind, name, what)
    for name, kind in optional.items():
        if item.get(name) is not None:
            out[name] = _typed(item[name], kind, name, what)
    return out


def _typed(value: Any, kind: type, name: str, what: str) -> Any:
    # `bool` is an `int` to Python, and `True` tokens is a count of one.
    if not isinstance(value, kind) or isinstance(value, bool):
        raise UnreadableReport(f"a {what}'s {name} is {value!r}, not {kind.__name__}")
    return value


def _parents_first(invocations: list[ExternalInvocation]) -> list[ExternalInvocation]:
    """Ordered so every parent precedes its children, or refused.

    The recorder refuses a child whose parent it has not yet written, which is
    what keeps a partial report from half-applying. Ordering here means a job
    that wrote its children first is not refused for the order alone; a parent
    that never appears, or a cycle, still is.
    """
    by_id = {i.local_id: i for i in invocations}
    if len(by_id) != len(invocations):
        raise UnreadableReport("two invocations share a local id")
    for invocation in invocations:
        if invocation.parent_local_id is not None and invocation.parent_local_id not in by_id:
            raise UnreadableReport(
                f"invocation {invocation.local_id!r} names parent "
                f"{invocation.parent_local_id!r}, which the report does not contain"
            )

    ordered: list[ExternalInvocation] = []
    placed: set[str] = set()
    remaining = list(invocations)
    while remaining:
        ready = [
            i for i in remaining
            if i.parent_local_id is None or i.parent_local_id in placed
        ]
        if not ready:
            raise UnreadableReport(
                "the report's invocations form a cycle: "
                + ", ".join(sorted(i.local_id for i in remaining))
            )
        for invocation in ready:
            ordered.append(invocation)
            placed.add(invocation.local_id)
        remaining = [i for i in remaining if i.local_id not in placed]
    return ordered
