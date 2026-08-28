"""Quarantine.

An entry whose policy the resolved profile cannot honor is never dispatched and
no run is created for it. Cloud-assisted work on the same profile continues
normally: a degraded profile reduces what runs, never what is guaranteed.

Quarantine is DERIVED from the current capability report rather than stored as
a status. Two consequences, both wanted:

  - Release is automatic. When the local reasoner comes back, previously
    blocked entries are eligible again with no manual re-entry and no
    reconciliation job that could itself fail.
  - There is no stored flag to go stale against reality. The blocked list is
    always the truth about right now.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..db.repository import Repository
from .capability import CapabilityReport
from .policy import PolicyResolution, resolve_policy


@dataclass(frozen=True, slots=True)
class Screening:
    """The decision for one entry under the current capability report."""

    entry_id: str
    entry_policy: str
    resolution: PolicyResolution

    @property
    def dispatchable(self) -> bool:
        return self.resolution.permitted

    @property
    def cause(self) -> str | None:
        return self.resolution.cause


class Quarantine:
    def __init__(self, repo: Repository, report: CapabilityReport) -> None:
        self._repo = repo
        self._report = report

    @property
    def report(self) -> CapabilityReport:
        return self._report

    def screen(
        self, entry_id: str, entry_policy: str, *, upgrade_decision_id: str | None = None
    ) -> Screening:
        availability = self._report.for_policy(entry_policy)
        resolution = resolve_policy(
            entry_policy,
            available=availability.available,
            unavailable_reason=availability.reason,
            upgrade_decision_id=upgrade_decision_id,
        )
        return Screening(
            entry_id=entry_id, entry_policy=entry_policy, resolution=resolution
        )

    def _screen_all(self) -> list[Screening]:
        return [
            self.screen(row["id"], row["default_policy"])
            for row in self._repo.dispatch_eligible_entries()
        ]

    def dispatchable(self) -> list[Screening]:
        """Entries the current profile can honor."""
        return [s for s in self._screen_all() if s.dispatchable]

    def blocked(self) -> list[Screening]:
        """Entries held back, each carrying the finding that caused it."""
        return [s for s in self._screen_all() if not s.dispatchable]
