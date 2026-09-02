"""The six stages, what each consumes, and when each may run.

This module is the proposal's blocking table as code, and it is meant to be
checkable against that table by eye. The table was built from what each stage
can actually call rather than from a rule imposed over the top, and the result
is deliberately not a chain:

    brief ──> everything          (nothing downstream has an input without it)
    build ──> critique            (nothing to critique produces nothing useful)

Every other edge is absent on purpose. `mockups` without `research` is degraded
but real; `build` without `mockups` is degraded but real. A uniform "each stage
blocks the next" rule would skip both whenever `research` is unavailable — which
is every night today, because no research provider exists — and would produce
empty mornings on exactly the nights principle 3 exists for.

`distill` does not fit the edge shape at all. It is blocked by *all* of its
predecessors failing, not by any one of them, which is why this is a predicate
per stage rather than a dependency list per stage.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

BRIEF = "brief"
RESEARCH = "research"
MOCKUPS = "mockups"
BUILD = "build"
CRITIQUE = "critique"
DISTILL = "distill"

#: Recorded when a stage is skipped rather than attempted. A stage that was
#: never attempted is not a stage that failed, and the morning should be able to
#: tell them apart.
#:
#: `research` carried this as a permanent `unavailable` until the capability
#: shipped on 2 Sep. It is now decided per run by whether a credential is
#: configured, so the skip is a fact about this deployment rather than about
#: the codebase — `night.research` records which of its three reasons applied.
NO_RESEARCH_PROVIDER = "no research provider is configured"


@dataclass(frozen=True, slots=True)
class Stage:
    """One stage: its position, the role that runs it, and its precondition."""

    name: str
    seq: int
    role: str
    #: True when this stage's inputs are present. Takes the set of stage names
    #: that reached `complete` so far, because that is exactly what the
    #: precondition is about — not what was attempted.
    can_run: Callable[[frozenset[str]], bool]
    #: Set where the stage cannot run at all yet, regardless of its inputs.
    unavailable: str | None = None
    #: The `artifacts.kind` this stage produces, or None where it produces no
    #: file. Stage names and artifact kinds are separate CHECK constraints that
    #: overlap in five of six places and differ in one; mapping them explicitly
    #: is what stops a rename of either from silently breaking the other.
    artifact_kind: str | None = None

    def blocked_reason(self, completed: frozenset[str]) -> str | None:
        """Why this stage cannot run, or None when it can."""
        if self.unavailable:
            return self.unavailable
        if not self.can_run(completed):
            return f"{self.name} needs an input no earlier stage produced"
        return None


#: In schema order, which is also execution order. The `stage` CHECK constraint
#: in `0001_initial.sql` is the authority on the names; `assert_matches_schema`
#: reads it rather than trusting this tuple.
STAGES: tuple[Stage, ...] = (
    Stage(BRIEF, 1, "researcher", lambda done: True, artifact_kind="brief"),
    # No longer permanently unavailable: `night.research` decides per run, and
    # a `local-only` run refuses before a query is ever constructed.
    Stage(
        RESEARCH,
        2,
        "researcher",
        lambda done: BRIEF in done,
        artifact_kind="research_digest",
    ),
    Stage(MOCKUPS, 3, "architect", lambda done: BRIEF in done, artifact_kind="mockup"),
    Stage(BUILD, 4, "builder", lambda done: BRIEF in done, artifact_kind="build"),
    Stage(CRITIQUE, 5, "critic", lambda done: BUILD in done, artifact_kind="critique"),
    # Not "all predecessors", not "the one before" — any evidence at all. A
    # night that produced one completed stage still taught the brain something.
    Stage(DISTILL, 6, "distiller", lambda done: bool(done), artifact_kind="summary"),
)

BY_NAME: dict[str, Stage] = {s.name: s for s in STAGES}


def assert_artifact_kinds_match_schema(conn: sqlite3.Connection) -> None:
    """Fail if a stage claims an artifact kind the schema does not permit.

    Stage names and artifact kinds are two separate CHECK constraints that
    overlap in five of six places and differ in one — `research` produces a
    `research_digest`. Mapping them by coincidence of name would break silently
    the first time either list moved.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'artifacts'"
    ).fetchone()
    if row is None:
        raise RuntimeError("no `artifacts` table; run migrations first")
    match = re.search(r"kind\s+TEXT\s+NOT NULL\s+CHECK\s*\(kind IN \(([^)]*)\)\)", row[0])
    if match is None:
        raise RuntimeError("the `artifacts` table has no readable kind CHECK constraint")
    permitted = set(re.findall(r"'([a-z_]+)'", match.group(1)))
    claimed = {s.artifact_kind for s in STAGES if s.artifact_kind}
    if not claimed <= permitted:
        raise RuntimeError(
            f"stages claim artifact kinds the schema forbids: "
            f"{sorted(claimed - permitted)}"
        )


def assert_matches_schema(conn: sqlite3.Connection) -> None:
    """Fail if the schema's stage set and this module's have diverged.

    Read from the CHECK constraint rather than restated, the same way
    `agents.roster.permitted_roles` reads its roles: a seventh stage added to
    the database with no definition here should fail a test, and it cannot if
    the test carries its own copy of the six.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'run_stages'"
    ).fetchone()
    if row is None:
        raise RuntimeError("no `run_stages` table; run migrations first")
    match = re.search(r"stage\s+TEXT\s+NOT NULL\s+CHECK\s*\(stage IN \(([^)]*)\)\)", row[0])
    if match is None:
        raise RuntimeError("the `run_stages` table has no readable stage CHECK constraint")
    in_schema = set(re.findall(r"'([a-z]+)'", match.group(1)))
    defined = set(BY_NAME)
    if in_schema != defined:
        raise RuntimeError(
            f"stages in the schema {sorted(in_schema)} do not match the stages "
            f"defined here {sorted(defined)}"
        )
