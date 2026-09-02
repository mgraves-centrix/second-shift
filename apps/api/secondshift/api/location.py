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


def location_path(path: str | Path | None = None) -> Path:
    """Where the location file is expected, by the same precedence as the read."""
    return Path(path or os.environ.get(ENV_LOCATION) or _DEFAULT_PATH)


def location_config_error(path: str | Path | None = None) -> str | None:
    """The parse failure in the location file, if it has one.

    An absent file is not an error — the celestial layer is optional. A file
    that exists and cannot be parsed is, and it used to be indistinguishable
    from the absent case, so an operator who mistyped it saw no coordinates and
    no reason.
    """
    resolved = location_path(path)
    try:
        tomllib.loads(resolved.read_text())
    except OSError:
        return None
    except tomllib.TOMLDecodeError as exc:
        return f"{resolved} is malformed: {exc}"
    return None


def home_location(path: str | Path | None = None) -> Home:
    """Configured home coordinates, or empty when none are set.

    Absent configuration is not an error. The celestial layer degrades to no
    sun position; capture must not fail because a rendering nicety is unset.
    A malformed file degrades the same way rather than raising, for the same
    reason — `location_config_error` is how it becomes visible.
    """
    resolved = location_path(path)
    try:
        home = tomllib.loads(resolved.read_text())["home"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return Home(None, None)
    return Home(
        lat=home.get("lat"), lon=home.get("lon"), label=home.get("label", "")
    )
