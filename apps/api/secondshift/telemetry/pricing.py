"""Cost computation from a git-tracked rate table.

Cost is computed at write time from the rate in effect at the call's timestamp,
so a historical curve is reproducible from the repository alone. Adding a new
rate with a later `effective_from` never changes a cost already recorded.

A missing rate raises. The cost curve is a scored measurement rather than a
display value, and a silent zero would understate it in exactly the direction
that flatters the project.

TOML rather than YAML: `tomllib` is in the standard library from Python 3.11,
and this project cannot afford another wheel to build on aarch64.
"""

from __future__ import annotations

import datetime as dt
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parents[4] / "config" / "pricing.toml"

WILDCARD = "*"


class MissingRate(LookupError):
    """No rate covers this provider, model and timestamp."""


@dataclass(frozen=True, slots=True)
class Rate:
    provider: str
    model: str
    effective_from_ms: int
    prompt_usd_per_mtok: float
    completion_usd_per_mtok: float
    note: str = ""


def _to_ms(value: str | dt.date) -> int:
    if isinstance(value, dt.datetime):
        moment = value if value.tzinfo else value.replace(tzinfo=dt.UTC)
    elif isinstance(value, dt.date):
        moment = dt.datetime(value.year, value.month, value.day, tzinfo=dt.UTC)
    else:
        moment = dt.datetime.fromisoformat(str(value)).replace(tzinfo=dt.UTC)
    return int(moment.timestamp() * 1000)


class PricingTable:
    """Rates keyed by provider and model, resolved by timestamp."""

    def __init__(self, rates: list[Rate]) -> None:
        # Newest first, so the first match is the rate in effect.
        self._rates = sorted(rates, key=lambda r: r.effective_from_ms, reverse=True)

    @classmethod
    def load(cls, path: str | Path | None = None) -> PricingTable:
        resolved = Path(
            path or os.environ.get("SECOND_SHIFT_PRICING") or _DEFAULT_PATH
        )
        if not resolved.exists():
            raise MissingRate(f"pricing table not found at {resolved}")
        raw = tomllib.loads(resolved.read_text())
        return cls(
            [
                Rate(
                    provider=entry["provider"],
                    model=entry["model"],
                    effective_from_ms=_to_ms(entry["effective_from"]),
                    prompt_usd_per_mtok=float(entry["prompt_usd_per_mtok"]),
                    completion_usd_per_mtok=float(entry["completion_usd_per_mtok"]),
                    note=entry.get("note", ""),
                )
                for entry in raw.get("rate", [])
            ]
        )

    def rate_for(self, provider: str, model: str, ts_ms: int) -> Rate:
        """The rate in effect for this call, preferring an exact model match."""
        candidates = [
            r
            for r in self._rates
            if r.provider == provider
            and r.effective_from_ms <= ts_ms
            and r.model in (model, WILDCARD)
        ]
        if not candidates:
            raise MissingRate(
                f"no rate for provider={provider!r} model={model!r} at ts={ts_ms}. "
                "Add an entry to config/pricing.toml; cost is never recorded as zero "
                "by default."
            )
        exact = [r for r in candidates if r.model == model]
        return (exact or candidates)[0]

    def cost_usd(
        self,
        *,
        provider: str,
        model: str,
        ts_ms: int,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        rate = self.rate_for(provider, model, ts_ms)
        return (
            prompt_tokens * rate.prompt_usd_per_mtok
            + completion_tokens * rate.completion_usd_per_mtok
        ) / 1_000_000
