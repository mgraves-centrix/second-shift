"""One module per capability, and every route the application serves.

The rule is one module per capability, and a path's first segment names it in
seven of the nine routes. The two that it does not:

- `/events/{id}` is in `night`, because it drills into a timeline and means
  nothing apart from one.
- `/decisions/{id}/answer` is in `morning`, because it is the interview's write
  side.

Both are the second noun of a capability that already owns a module. A rule with
two stated exceptions is more honest than a rule that would put four files where
two belong.

`ROUTERS` is the registration order, and it is also match order: every one of
these is included before the exported web surface is mounted, so an API path is
never answered by the page.
"""

from __future__ import annotations

from fastapi import APIRouter

from . import artifacts, capture, morning, night, system

#: In the order they are included. Nothing depends on the order between them —
#: no two declare overlapping paths — but the list is the one place to look for
#: what the application serves.
ROUTERS: tuple[APIRouter, ...] = (
    system.router,
    capture.router,
    night.router,
    morning.router,
    artifacts.router,
)

__all__ = ["ROUTERS"]
