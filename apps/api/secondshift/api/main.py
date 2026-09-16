"""ASGI entry point.

    uvicorn secondshift.api.main:app

Configuration is environment-only, so the same module serves the personal
instance and the judge deployment without a branch.
"""

from __future__ import annotations

import os

from ..config import synthetic_flag
from .app import build_context, create_app

DEFAULT_DB = os.path.expanduser("~/second-shift-data/second-shift.db")

db_path = os.environ.get("SECOND_SHIFT_DB", DEFAULT_DB)
os.makedirs(os.path.dirname(db_path), exist_ok=True)

#: Server-derived, never accepted from a request. The judge deployment sets it
#: so its seeded persona can never contaminate a real measurement. Strict: an
#: unrecognized value raises here rather than resolving to false.
is_synthetic = synthetic_flag()

app = create_app(build_context(db_path, is_synthetic=is_synthetic))
