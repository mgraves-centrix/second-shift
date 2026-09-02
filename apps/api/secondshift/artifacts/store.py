"""Writing artifacts: bytes to disk first, then the row that describes them.

`content_sha` and `bytes` are computed from the file **as read back**, never from
the string that was passed in. A hash of the intent proves what was meant, not
what landed — and a truncated write, a full disk or an encoding surprise all
produce a row that is confidently wrong about a file nobody has checked. That
column exists to detect exactly those, so it has to be derived from the artifact
rather than from its source.

A failed write raises before any row exists. The same rule `agents.roster`
applies to prompt files, for the same reason: a row pointing at a file that is
not there records a provenance nobody can check, which is the same defect as
recording none while looking like it did.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from ..db.repository import Repository

ENV_ARTIFACTS = "SECOND_SHIFT_ARTIFACTS"

#: One file name per single-artifact kind. `mockup` and `build` are absent
#: because they are variants and live in a directory each — see `variant_dir`.
_FILENAMES: dict[str, str] = {
    "brief": "brief.md",
    "research_digest": "research-digest.md",
    "critique": "critique.md",
    "summary": "summary.md",
}

#: Kinds produced as parallel variants rather than as one file.
VARIANT_KINDS = frozenset({"mockup", "build"})


class ArtifactWriteFailed(RuntimeError):
    """The file could not be written, so no row was recorded."""


def default_root() -> Path:
    """Where artifacts live when nothing says otherwise: beside the database."""
    return Path(os.path.expanduser("~/second-shift-data/artifacts"))


def artifact_root() -> Path:
    """The configured root. Deployment-specific, which is why it is not stored.

    The judge instance runs this same code against a different root, so the row
    holds a path relative to here. An absolute path in a row would also pin a
    home directory into data a judge reads, which
    `scripts/check-no-environment.sh` exists because of.
    """
    return Path(os.environ.get(ENV_ARTIFACTS) or default_root())


@dataclass(frozen=True, slots=True)
class WrittenArtifact:
    """What landed, and the row that describes it."""

    artifact_id: str
    #: Relative to the root, which is what the database stores.
    path: str
    content_sha: str
    bytes: int

    def absolute(self, root: Path | None = None) -> Path:
        return (root or artifact_root()) / self.path


def relative_path(
    *, night_of: str, run_id: str, kind: str, variant_index: int | None = None
) -> str:
    """Where an artifact of this kind belongs, relative to the root.

    Keyed on `run_id` rather than on the entry: a re-run of the same idea on a
    later night must not overwrite what the first night produced. `night_of`
    leads so a person can list a date by hand — a directory nobody can navigate
    is the opaque store the constitution forbids, in a different format.
    """
    base = f"{night_of}/{run_id}"
    if kind in VARIANT_KINDS:
        if variant_index is None:
            raise ValueError(f"{kind} is a variant kind and needs a variant_index")
        suffix = "index.html" if kind == "mockup" else "build.md"
        return f"{base}/{kind}/{variant_index}/{suffix}"
    if variant_index is not None:
        raise ValueError(f"{kind} is not a variant kind but was given an index")
    try:
        return f"{base}/{_FILENAMES[kind]}"
    except KeyError as exc:
        raise ValueError(f"no filename is defined for artifact kind {kind!r}") from exc


def write_artifact(
    repo: Repository,
    *,
    run_id: str,
    entry_id: str,
    night_of: str,
    stage: str,
    kind: str,
    content: str,
    produced_by_invocation_id: str | None = None,
    variant_group: str | None = None,
    variant_index: int | None = None,
    is_synthetic: bool = False,
    root: Path | None = None,
) -> WrittenArtifact:
    """Write the file, then record what actually landed.

    `variant_rank` is deliberately not a parameter. A rank is what a critic
    produced and it does not exist yet at write time — which is what makes it
    impossible for this function to default it to the generation index, the
    failure the whole capability is written against.
    """
    relative = relative_path(
        night_of=night_of, run_id=run_id, kind=kind, variant_index=variant_index
    )
    target = (root or artifact_root()) / relative
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        landed = target.read_bytes()
    except OSError as exc:
        raise ArtifactWriteFailed(f"could not write {relative}: {exc}") from exc

    artifact_id = repo.insert_artifact(
        run_id=run_id,
        entry_id=entry_id,
        stage=stage,
        kind=kind,
        path=relative,
        variant_group=variant_group,
        variant_index=variant_index,
        content_sha=hashlib.sha256(landed).hexdigest(),
        artifact_bytes=len(landed),
        produced_by_invocation_id=produced_by_invocation_id,
        is_synthetic=is_synthetic,
    )
    return WrittenArtifact(
        artifact_id=artifact_id,
        path=relative,
        content_sha=hashlib.sha256(landed).hexdigest(),
        bytes=len(landed),
    )


def verify(row, *, root: Path | None = None) -> bool:
    """Does the file still hash to what was recorded?

    False for a file that changed, was truncated, or is gone. Returned rather
    than raised: a caller checking a night's artifacts wants the list of the ones
    that no longer match, not to stop at the first.
    """
    path = (root or artifact_root()) / row["path"]
    try:
        landed = path.read_bytes()
    except OSError:
        return False
    return (
        hashlib.sha256(landed).hexdigest() == row["content_sha"]
        and len(landed) == row["bytes"]
    )
