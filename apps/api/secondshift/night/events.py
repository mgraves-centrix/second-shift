"""What a night records as it happens.

Nothing in `night/` wrote an `events` row until 19 Sep. A six-stage run produced
six invocations, six model calls and **no timeline at all**, so the night view —
the signature screen — rendered nothing for a real night and everything for a
seeded one. It was not a spec violation: `telemetry` requires events be
renderable without parsing and never said the night must emit them, and the
browser gate passes because it drives seeded data.

Its own module because both `run.py` and `output.py` write events and the
research stage lives in the latter; importing across them would be a cycle.
"""

from __future__ import annotations

from ..telemetry.recorder import Recorder


def _stage_event(
    recorder: Recorder,
    *,
    run_id: str,
    lane: str,
    kind: str,
    label: str,
    severity: str = "info",
    duration_ms: int | None = None,
) -> None:
    """Record one timeline event for this stage. Never fails the stage.

    `run_id` is passed explicitly because a stage boundary has no invocation
    producing it, so the recorder's context is empty and the event would be
    written with no run — invisible to the timeline, which queries by run.

    The lane is the lane the work belonged to, never the role of whatever
    produced the row: a stage boundary has no producer at all, so it is
    `system`. `night-timeline`'s spec says exactly this about reading lanes and
    it holds for writing them too.

    Wrapped because telemetry must not be able to cost a night its work. A stage
    that produced an artifact and then failed to describe itself is still a
    stage that produced an artifact.
    """
    try:
        recorder.record_event(
            lane=lane,
            kind=kind,
            label=label,
            severity=severity,
            duration_ms=duration_ms,
            run_id=run_id,
        )
    except Exception:  # noqa: BLE001 - a night is not lost over its own telemetry
        pass
