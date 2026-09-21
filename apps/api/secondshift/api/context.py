"""What a request handler needs, resolved once at startup.

Separated from `app.py` because a route module declared at import time cannot
close over a value that does not exist until `create_app` runs. The context
therefore lives on the application and is read from the request, which is the
only one of the three available shapes that keeps two applications in one
process independent — a module global does not, and a router built by a factory
turns every route module into a function that has to be called before it can be
looked at.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from ..airlock.capability import CapabilityReport, build_report
from ..config import ResolvedProfile, resolve_profile
from ..db.connection import connect
from ..db.migrate import migrate
from ..db.repository import Repository
from ..telemetry.pricing import PricingTable
from ..telemetry.recorder import Recorder


@dataclass
class Context:
    """Everything a request handler needs, resolved once at startup."""

    repo: Repository
    recorder: Recorder
    profile: ResolvedProfile
    report: CapabilityReport
    is_synthetic: bool


def build_context(
    db_path: str,
    *,
    is_synthetic: bool = False,
    profile: ResolvedProfile | None = None,
) -> Context:
    conn = connect(db_path)
    migrate(conn)
    repo = Repository(conn)
    resolved = profile if profile is not None else resolve_profile()
    return Context(
        repo=repo,
        recorder=Recorder(
            repo, pricing=PricingTable.load(), compute_profile=str(resolved.profile)
        ),
        profile=resolved,
        report=build_report(resolved),
        is_synthetic=is_synthetic,
    )


def get_context(request: Request) -> Context:
    """The context `create_app` was given, for the application handling this."""
    return request.app.state.context
