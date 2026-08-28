"""Deterministic synthetic nights.

The night scrubber cannot be built against four real events, and real nights
will not be dense until the orchestrator exists. This writes one that is:
structurally identical to real telemetry, reproducible from a seed, and marked
`is_synthetic` on every row so measurement never sees it.

    from secondshift_seed import generate_night
    night = generate_night(repository, seed=7)

The same generator seeds the judge deployment, which is why it writes through
the repository layer rather than shortcutting to SQL: a demo built on rows the
system could not itself produce is a demo of something else.
"""

from __future__ import annotations

from .night import DEFAULT_NIGHT_OF, GeneratedNight, generate_night

__all__ = ["DEFAULT_NIGHT_OF", "GeneratedNight", "generate_night"]
