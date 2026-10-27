"""Retaining what a model call said, as opposed to what it cost.

`model_calls` records the cost of a completion. This records its content. A
token count cannot be reconstructed into a prompt, so a completion that runs
before retention exists is permanently unreadable and permanently untrainable —
which is ADR 0007's argument for capturing payloads from day one, and the reason
six nights of this project's own history cannot be read back.

Text lives on disk behind a path reference. Contexts run to a million tokens,
and payload text in SQLite would dominate every query plan in a database whose
other tables are small, indexed and read constantly.

The same shape as `artifacts/store.py`, deliberately: a configured root, a
relative path in the row, and byte counts computed from the files **as read
back**. A count derived from the text passed in proves what was meant rather
than what landed, and a truncated write or a full disk then produces a row that
is confidently wrong about a file nobody has checked.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ENV_PAYLOADS = "SECOND_SHIFT_PAYLOADS"


class PayloadWriteFailed(OSError):
    """The files could not be written, so no row should exist.

    An `OSError` rather than a sibling of `ArtifactWriteFailed`, because the one
    caller catches `OSError` and records the failure instead of raising: the
    completion is the product and this is evidence about it.
    """


def default_root() -> Path:
    """Where payloads live when nothing says otherwise: beside the artifacts."""
    return Path(os.path.expanduser("~/second-shift-data/payloads"))


def payload_root() -> Path:
    """The configured root. Deployment-specific, which is why it is not stored.

    The judge instance runs this same code against a different root, so the row
    holds a path relative to here. An absolute path in a row would also pin a
    home directory into data a judge reads, which
    `scripts/check-no-environment.sh` exists because of.
    """
    return Path(os.environ.get(ENV_PAYLOADS) or default_root())


@dataclass(frozen=True, slots=True)
class RetainedPayload:
    """What landed, as the row will describe it."""

    #: Both relative to the root, which is what the database stores.
    prompt_path: str
    completion_path: str
    prompt_bytes: int
    completion_bytes: int


def relative_paths(model_call_id: str, ts_ms: int) -> tuple[str, str]:
    """Where a call's two files belong, relative to the root.

    Keyed on the call id, which is a ULID and so already unique and already
    sorts by time. Grouped by month so that one night's files are findable by
    hand and no single directory grows without bound — a directory nobody can
    navigate is the opaque store the constitution forbids, in a different
    format.

    The month comes from the call's own timestamp rather than from the clock, so
    a payload retained for externally-attributed work filed under last month's
    timestamp lands in last month's directory.
    """
    month = datetime.fromtimestamp(ts_ms / 1000, UTC).strftime("%Y-%m")
    return (
        f"{month}/{model_call_id}.prompt.json",
        f"{month}/{model_call_id}.completion.json",
    )


def write_payload(
    *,
    model_call_id: str,
    ts_ms: int,
    prompt: object,
    completion: object,
    root: Path | None = None,
) -> RetainedPayload:
    """Write both files, then report what actually landed.

    Raises before anything has been recorded. A row pointing at a file that is
    not there records a provenance nobody can check, which is the same defect as
    recording none while looking like it did.
    """
    relative_prompt, relative_completion = relative_paths(model_call_id, ts_ms)
    base = root or payload_root()
    try:
        landed = []
        for relative, content in (
            (relative_prompt, prompt),
            (relative_completion, completion),
        ):
            target = base / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(content, ensure_ascii=False, indent=1))
            landed.append(len(target.read_bytes()))
    except OSError as exc:
        raise PayloadWriteFailed(
            f"could not retain the payload for {model_call_id}: {exc}"
        ) from exc
    return RetainedPayload(
        prompt_path=relative_prompt,
        completion_path=relative_completion,
        prompt_bytes=landed[0],
        completion_bytes=landed[1],
    )
