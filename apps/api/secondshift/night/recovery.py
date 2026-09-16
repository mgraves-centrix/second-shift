"""What a night killed mid-run left open, closed at the start of the next one.

`run_entry` closes its run and returns its entry in a `finally`, and a SIGKILL,
an OOM or a power cut skips every `finally` there is. What that leaves is an
entry in `running`, which nothing dispatches and nothing lists — the idea
disappears from the night and from the report of what the night did not run —
beside a run and a stage that read as permanently in flight.

This runs only under the night lock. Closing open runs is correct precisely
because no other night can be holding them, and without the lock it would
close a live night's work out from under it.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..db.repository import Repository


@dataclass(frozen=True, slots=True)
class Recovered:
    run_id: str
    entry_id: str


def recover_interrupted(repo: Repository) -> list[Recovered]:
    """Close every open stage and run as `failed`, and return their entries to the queue.

    Each close goes through the repository's named operation, so recovery
    cannot write anything a normal night could not. Synthetic rows are left
    alone: the seed deliberately writes a night still in flight so the timeline
    can render one. A run recovered here is
    `failed` because nothing proves any of it finished: a stage that completed
    before the kill already has its own end time and keeps it.
    """
    for stage in repo.connection.execute(
        "SELECT s.id FROM run_stages s JOIN runs r ON r.id = s.run_id "
        "WHERE s.ended_at_ms IS NULL AND r.ended_at_ms IS NULL AND r.is_synthetic = 0"
    ).fetchall():
        repo.complete_run_stage(stage["id"], status="failed")

    recovered: list[Recovered] = []
    for run in repo.connection.execute(
        "SELECT id, entry_id FROM runs WHERE ended_at_ms IS NULL AND is_synthetic = 0 "
        "ORDER BY started_at_ms, id"
    ).fetchall():
        repo.close_run(run["id"], outcome="failed")
        recovered.append(Recovered(run["id"], run["entry_id"]))

    for entry in repo.connection.execute(
        "SELECT id FROM entries WHERE status = 'running' AND is_synthetic = 0"
    ).fetchall():
        repo.transition_entry(entry["id"], to_status="queued")
    return recovered
