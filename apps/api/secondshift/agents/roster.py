"""The roster: six roles, their prompt files, and the pinning that makes an
eight-week curve mean something.

`prompt_sha` is computed here from file content and nowhere else. It exists so
that an improving curve can be shown to measure the brain rather than a prompt
someone edited on day 40, and the only thing writing it before this module was a
test fixture writing `deadbeef` against a path that never existed.

Prompt files are append-only. A changed prompt is `<role>.v2.md` beside the
first, never an edit in place — the schema says so (`0001_initial.sql`: "a
prompt change is a new version") and `config/evals/rubric.md` reached the same
conclusion for the same reason.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ..db.repository import Repository

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
REPO_ROOT = Path(__file__).resolve().parents[4]

#: Filename shape: `<role>.v<n>.md`. The version lives in the name so that
#: "which text produced this invocation" is answerable without a database.
_FILENAME = re.compile(r"^(?P<role>[a-z]+)\.v(?P<version>\d+)\.md$")


class PromptFileMissing(RuntimeError):
    """A roster entry names a prompt file that is not there.

    Raised rather than registered. A row pointing at an absent file records a
    provenance nobody can check, which is the same defect as recording no
    provenance while looking like it did.
    """


class PromptEditedInPlace(RuntimeError):
    """A registered version's file no longer hashes to what was recorded.

    The same guard `reconcile-rubric-pinning` put on the rubric. An edit in
    place silently redefines what every prior invocation was measuring.
    """


@dataclass(frozen=True, slots=True)
class PromptFile:
    role: str
    version: int
    path: Path

    @property
    def sha(self) -> str:
        return sha256_of(self.path)


def sha256_of(path: Path) -> str:
    """The hash of a prompt's bytes. Never of anything else."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise PromptFileMissing(f"prompt file {path} cannot be read: {exc}") from exc


def permitted_roles(conn: sqlite3.Connection) -> set[str]:
    """The roles the schema allows, read from the CHECK constraint itself.

    Read rather than restated: a seventh role added to the database with no
    prompt behind it should fail the roster's own test, and it cannot if the
    test carries its own copy of the list.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'agents'"
    ).fetchone()
    if row is None:
        raise RuntimeError("no `agents` table; run migrations first")
    match = re.search(r"role\s+TEXT\s+NOT NULL\s+CHECK\s*\(role IN \(([^)]*)\)\)", row[0])
    if match is None:
        raise RuntimeError("the `agents` table has no readable role CHECK constraint")
    return set(re.findall(r"'([a-z]+)'", match.group(1)))


def discover(directory: Path = PROMPTS_DIR) -> dict[str, PromptFile]:
    """The highest version of each role's prompt, by filename.

    A malformed filename raises rather than being skipped, for the reason the
    migration runner refuses one: a file silently ignored is a prompt nobody
    notices is not in effect.
    """
    found: dict[str, PromptFile] = {}
    for path in sorted(directory.glob("*.md")):
        match = _FILENAME.match(path.name)
        if match is None:
            raise ValueError(
                f"prompt filename {path.name!r} is not <role>.v<n>.md — refusing "
                "to skip it, because a skipped prompt is one nobody notices is "
                "not in effect"
            )
        role = match.group("role")
        version = int(match.group("version"))
        current = found.get(role)
        if current is None or version > current.version:
            found[role] = PromptFile(role=role, version=version, path=path)
    return found


def _recorded_path(path: Path) -> str:
    """Repository-relative where possible, absolute otherwise.

    A relative path is what a reader wants; an absolute one is what a test
    directory outside the tree can honestly offer. Guessing at a relative path
    that does not resolve would be worse than either.
    """
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def register(repo: Repository, *, directory: Path = PROMPTS_DIR) -> dict[str, str]:
    """Register every role's current prompt. Returns role -> agent id.

    Idempotent: unchanged files write nothing on a second call, which is what
    makes this safe to run at every startup. That idempotence is why the hash
    comparison is a refusal rather than an insert — the two cases it has to
    tell apart are "already registered" and "edited in place", and they differ
    only by the hash.
    """
    registered: dict[str, str] = {}
    for role, prompt in sorted(discover(directory).items()):
        if not prompt.path.exists():
            raise PromptFileMissing(f"prompt file {prompt.path} does not exist")
        sha = prompt.sha
        existing = repo.get_agent(role, prompt.version)
        if existing is not None:
            if existing["prompt_sha"] != sha:
                raise PromptEditedInPlace(
                    f"{prompt.path.name} was registered at "
                    f"{existing['prompt_sha'][:12]} and now hashes to "
                    f"{sha[:12]}. A prompt is append-only: supersede it with "
                    f"{role}.v{prompt.version + 1}.md rather than editing it, "
                    "or every invocation recorded against this version is "
                    "pinned to text that no longer exists."
                )
            registered[role] = existing["id"]
            continue
        registered[role] = repo.insert_agent(
            name=role,
            role=role,
            version=prompt.version,
            prompt_path=_recorded_path(prompt.path),
            prompt_sha=sha,
        )
    return registered
