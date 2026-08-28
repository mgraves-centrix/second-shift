"""Home coordinates, read from configuration.

Never a browser geolocation prompt: capture is the interaction that must stay
frictionless, and a permission dialog is a cost paid on every capture to serve a
rendering detail on the night view.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

ENV_LOCATION = "SECOND_SHIFT_LOCATION"
_DEFAULT_PATH = Path(__file__).resolve().parents[4] / "config" / "location.toml"


@dataclass(frozen=True, slots=True)
class Home:
    lat: float | None
    lon: float | None
    label: str = ""


def home_location(path: str | Path | None = None) -> Home:
    """Configured home coordinates, or empty when none are set.

    Absent configuration is not an error. The celestial layer degrades to no
    sun position; capture must not fail because a rendering nicety is unset.
    """
    resolved = Path(path or os.environ.get(ENV_LOCATION) or _DEFAULT_PATH)
    try:
        home = tomllib.loads(resolved.read_text())["home"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return Home(None, None)
    return Home(
        lat=home.get("lat"), lon=home.get("lon"), label=home.get("label", "")
    )
