"""Where a model call's prompt and completion are kept.

`model_calls` records what a call cost; `model_call_payloads` records what it
said. ADR 0007 put the second table in the first migration so that capture would
start on day one, and then nothing called its insert: six real nights and the
first scored eval run left no text behind, and a judgement the parser refused
could be described only by the character offset it died at. A token count cannot
be turned back into what a model was asked or what it answered, which is why
this runs on every completion rather than as a later pass.

Text lives on disk beside the database and the row holds a path relative to the
root, for the reason artifact paths are relative: the judge instance runs this
code against a different root, and an absolute path would pin a home directory
into a row.

Local by construction. `0001_initial.sql` says these files must never be synced,
uploaded, or present in a judge deployment; `deploy/judge/Dockerfile` copies an
allowlist that cannot reach this directory.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ENV_PAYLOADS = "SECOND_SHIFT_PAYLOADS"


def default_root() -> Path:
    """Beside the database, as the artifact root is."""
    return Path(os.path.expanduser("~/second-shift-data/payloads"))


def payload_root() -> Path:
    """The configured root, resolved at the call rather than at import.

    Read on every write so a process that sets the variable after importing —
    every test, through conftest — writes where it said rather than where the
    module happened to look first.
    """
    return Path(os.environ.get(ENV_PAYLOADS) or default_root())


@dataclass(frozen=True, slots=True)
class WrittenPayload:
    """What landed. Paths relative to the root; sizes read back from disk."""

    prompt_path: str
    completion_path: str
    prompt_bytes: int
    completion_bytes: int


def write_payload(
    root: Path,
    model_call_id: str,
    *,
    prompt: list[dict[str, str]],
    completion: str,
    finish_reason: str,
    ts_ms: int,
) -> WrittenPayload:
    """Write both halves of one call, under a month directory.

    By month because the directory is read rarely and appended to forever, and
    a flat directory of a few hundred thousand files is slow to list on the NFS
    share backups land on.

    The finish reason travels with the text. A completion that stopped at a
    token limit is refused before it is parsed, and read back without the
    reason it looks like a model that wrote half an answer on purpose.

    Raises `OSError` if either file cannot be written; the caller decides what
    a failed write costs.
    """
    month = datetime.fromtimestamp(ts_ms / 1000, tz=UTC).strftime("%Y-%m")
    prompt_rel = f"{month}/{model_call_id}.prompt.json"
    completion_rel = f"{month}/{model_call_id}.completion.json"

    (root / month).mkdir(parents=True, exist_ok=True)
    (root / prompt_rel).write_text(
        json.dumps({"messages": prompt}, ensure_ascii=False), encoding="utf-8"
    )
    (root / completion_rel).write_text(
        json.dumps(
            {"text": completion, "finish_reason": finish_reason}, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    return WrittenPayload(
        prompt_path=prompt_rel,
        completion_path=completion_rel,
        prompt_bytes=(root / prompt_rel).stat().st_size,
        completion_bytes=(root / completion_rel).stat().st_size,
    )
