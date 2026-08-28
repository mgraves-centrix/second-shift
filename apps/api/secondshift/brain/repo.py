"""Git access to the brain.

Four operations — head, status, add, commit — each a subprocess scoped with
`-C`. A git library would add a dependency and an object model to do what these
already do, against a repository chosen for being ordinary.

Nothing here may be called from a request handler. A git invocation in an HTTP
path makes the one interaction that must never fail depend on a lock file, a
subprocess and a disk.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

ENV_BRAIN = "SECOND_SHIFT_BRAIN"

#: Sibling of the code repository. Deliberately relative — a real path is
#: someone's environment and does not belong in a public repository.
_DEFAULT = Path(__file__).resolve().parents[4].parent / "second-shift-brain"

JOURNAL_DIR = "journal"
PROFILE = "profile.md"
STYLE_GUIDE = "style-guide.md"
SKILLS_DIR = "skills"


class BrainUnavailable(RuntimeError):
    """The brain is missing, unreadable, or not a git repository.

    Raised rather than returned so a caller cannot proceed as though the brain
    were merely empty. A brain silently not written is indistinguishable from a
    brain with nothing to write, until the eight-week diff is empty.
    """


@dataclass(frozen=True, slots=True)
class TopicFiles:
    """What the brain currently believes, as text."""

    profile: str
    style_guide: str
    skills: dict[str, str]


def brain_path(path: str | Path | None = None) -> Path:
    return Path(path or os.environ.get(ENV_BRAIN) or _DEFAULT)


class BrainRepo:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = brain_path(path)

    # -- availability ------------------------------------------------------

    @property
    def available(self) -> bool:
        return (self.path / ".git").exists()

    def require(self) -> None:
        if not self.path.exists():
            raise BrainUnavailable(f"brain path does not exist: {self.path}")
        if not (self.path / ".git").exists():
            raise BrainUnavailable(f"brain path is not a git repository: {self.path}")

    # -- git ---------------------------------------------------------------

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.path), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise BrainUnavailable(
                f"git {' '.join(args)} failed in {self.path}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        return result.stdout

    def head(self) -> str | None:
        """The brain's current commit, or None when it cannot be read.

        None rather than a placeholder: a synthetic value would later be
        indistinguishable from a real state, and the whole point of pinning is
        that a recorded commit means something.
        """
        if not self.available:
            return None
        try:
            return self._git("rev-parse", "HEAD").strip() or None
        except BrainUnavailable:
            return None

    def dirty_paths(self) -> list[str]:
        """Paths with uncommitted changes, from porcelain status."""
        self.require()
        return [
            line[3:].strip()
            for line in self._git("status", "--porcelain").splitlines()
            if line.strip()
        ]

    def commit_paths(self, paths: list[str], message: str) -> str | None:
        """Stage the given paths and commit them. Returns the new commit, or None.

        Stages *paths*, never the tree. That single choice is what keeps a
        hand-edited topic file out of an automated commit, and it is what makes
        sync safe to run on a timer against a repository someone is editing.
        """
        self.require()
        self._git("add", "--", *paths)
        staged = self._git("diff", "--cached", "--name-only").strip()
        if not staged:
            return None
        self._git("commit", "-m", message)
        return self.head()

    # -- topic files -------------------------------------------------------

    def topic_files_at(self, commit: str) -> TopicFiles:
        """What the brain believed at a particular commit.

        Scoring a week-1 baseline means generating from the week-1 brain. Reading
        the working tree instead would pin a commit the output was never produced
        from, which makes the pinning decorative — the number would be labeled
        with a state that did not shape it.
        """
        self.require()

        def read(name: str) -> str:
            try:
                return self._git("show", f"{commit}:{name}")
            except BrainUnavailable:
                return ""  # absent at that commit is a younger brain, not an error

        listing = ""
        try:
            listing = self._git("ls-tree", "--name-only", f"{commit}:{SKILLS_DIR}")
        except BrainUnavailable:
            pass
        skills = {
            name.removesuffix(".md"): read(f"{SKILLS_DIR}/{name}")
            for name in listing.split()
            if name.endswith(".md") and name.upper() != "README.MD"
        }
        return TopicFiles(
            profile=read(PROFILE), style_guide=read(STYLE_GUIDE), skills=skills
        )

    def topic_files(self) -> TopicFiles:
        """Read what the brain believes. A missing file is a new brain, not a broken one."""
        self.require()

        def read(name: str) -> str:
            candidate = self.path / name
            return candidate.read_text() if candidate.is_file() else ""

        skills: dict[str, str] = {}
        skills_dir = self.path / SKILLS_DIR
        if skills_dir.is_dir():
            for skill in sorted(skills_dir.glob("*.md")):
                if skill.name.upper() == "README.MD":
                    continue  # the directory's own instructions are not a skill
                skills[skill.stem] = skill.read_text()

        return TopicFiles(
            profile=read(PROFILE), style_guide=read(STYLE_GUIDE), skills=skills
        )
