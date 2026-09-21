"""Rows and reports, as the response models want them.

Outside the route modules because `capability_payload` has callers in two of
them, and a route module importing another route module is the collision this
package exists to remove. The other three are here beside it so the rule stays
"a route module holds routes", with nothing to remember about which mapper lives
where.
"""

from __future__ import annotations

import sqlite3

from ..airlock.capability import CapabilityReport
from .schemas import (
    CapabilityResponse,
    EntryResponse,
    ModelCallResponse,
    PolicyAvailabilityResponse,
    RunSummaryResponse,
)


def capability_payload(report: CapabilityReport) -> CapabilityResponse:
    return CapabilityResponse(
        profile=str(report.profile),
        degraded=report.degraded,
        degradation_reason=report.degradation_reason,
        policies=[
            PolicyAvailabilityResponse(
                policy=str(a.policy), available=a.available, reason=a.reason
            )
            for a in report.policies
        ],
    )


def run_summary(row: sqlite3.Row) -> RunSummaryResponse:
    keys = row.keys()
    return RunSummaryResponse(
        id=row["id"],
        night_of=row["night_of"],
        started_at_ms=row["started_at_ms"],
        ended_at_ms=row["ended_at_ms"],
        effective_policy=row["effective_policy"],
        compute_profile=row["compute_profile"],
        outcome=row["outcome"],
        furthest_stage=row["furthest_stage"],
        is_synthetic=bool(row["is_synthetic"]),
        # Present when the row came from `list_runs`, which computes the frame.
        first_event_ms=row["first_event_ms"] if "first_event_ms" in keys else None,
        last_event_end_ms=row["last_event_end_ms"] if "last_event_end_ms" in keys else None,
        event_count=row["event_count"] if "event_count" in keys else 0,
        captured_tz=row["captured_tz"] if "captured_tz" in keys else None,
        tz_offset_min=row["tz_offset_min"] if "tz_offset_min" in keys else None,
    )


def model_call(row: sqlite3.Row) -> ModelCallResponse:
    return ModelCallResponse(
        id=row["id"],
        ts_ms=row["ts_ms"],
        provider=row["provider"],
        model=row["model"],
        policy=row["policy"],
        prompt_tokens=row["prompt_tokens"],
        completion_tokens=row["completion_tokens"],
        total_tokens=row["total_tokens"],
        estimated_cost_usd=row["estimated_cost_usd"],
        latency_ms=row["latency_ms"],
    )


def entry_response(row: sqlite3.Row, *, duplicate: bool) -> EntryResponse:
    return EntryResponse(
        id=row["id"],
        created_at_ms=row["created_at_ms"],
        received_at_ms=row["received_at_ms"],
        captured_tz=row["captured_tz"],
        policy=row["default_policy"],
        status=row["status"],
        title=row["title"],
        text=row["raw_text"],
        duplicate=duplicate,
    )
