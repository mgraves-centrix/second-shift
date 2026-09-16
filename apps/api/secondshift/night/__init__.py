"""The night: a checkpointed walk over six stages, per entry.

Principle 3 is executable here and nowhere else. `run_stages` existed from the
first migration and nothing wrote it; `Repository.close_run` existed and had no
caller, so every run the system could record sat permanently in flight.
"""

from .run import NightResult, Quarantined, StageResult, run_entry
from .stages import (
    BY_NAME,
    STAGES,
    Stage,
    assert_artifact_kinds_match_schema,
    assert_matches_schema,
)

__all__ = [
    "BY_NAME",
    "NightResult",
    "Quarantined",
    "STAGES",
    "Stage",
    "StageResult",
    "assert_artifact_kinds_match_schema",
    "assert_matches_schema",
    "run_entry",
]
