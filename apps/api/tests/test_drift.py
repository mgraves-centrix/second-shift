"""The checker that holds the claims a machine can hold.

Every check here is exercised against a constructed repository rather than
against this one, so a test cannot pass because the real tree happens to be
right today — and cannot start failing because somebody legitimately added a
directory.

The false-positive test is the one that decides whether anybody keeps this gate.
A check that fires on prose it misread is a check that gets suppressed, and a
suppressed check is worse than an absent one because its row still reads green.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKER = REPO_ROOT / "scripts" / "check-drift.py"

_TREE = """# Architecture

```
second-shift/
├── apps/
│   ├── api/                     the orchestrator
│   └── web/                     the PWA            {web_note}
└── scripts/
```
"""


@pytest.fixture
def repo(tmp_path):
    """A repository shaped like this one, with only what the checker reads."""

    def _build(*, web_note: str = "", extra: dict[str, str] | None = None,
               build_web: bool = True) -> Path:
        root = tmp_path / "repo"
        (root / "docs").mkdir(parents=True)
        (root / "apps" / "api").mkdir(parents=True)
        if build_web:
            (root / "apps" / "web").mkdir(parents=True)
        (root / "scripts").mkdir(parents=True)
        (root / "openspec" / "specs").mkdir(parents=True)
        (root / "openspec" / "changes" / "archive").mkdir(parents=True)
        (root / "docs" / "ARCHITECTURE.md").write_text(_TREE.format(web_note=web_note))
        for name, body in (extra or {}).items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
        subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
        return root

    return _build


def _checker_for(root: Path) -> Path:
    """Copy the checker into the constructed repository, and run *that* copy.

    It derives its root from its own location, which is what makes it runnable
    from anywhere — and the thing a test has to arrange around. The first draft
    of this file ran the real script with `cwd` set to the constructed tree,
    which quietly checked this repository instead: nine tests passed because the
    real tree is green, and only the five expecting a failure noticed.
    """
    copied = root / "scripts" / "check-drift.py"
    copied.write_text(CHECKER.read_text())
    return copied


def run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(root / "scripts" / "check-drift.py")],
        cwd=root,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin"},
    )


class TestTheDocumentedTree:
    def test_a_path_that_does_not_exist_fails(self, repo):
        root = repo(build_web=False)
        _checker_for(root)

        result = run(root)

        assert result.returncode == 1
        assert "apps/web is asserted and does not exist" in result.stderr

    def test_shipped_work_still_marked_planned_fails(self, repo):
        """The direction the 16 Sep pass left behind. A reader is being told
        work remains that does not."""
        root = repo(web_note="(planned)")
        _checker_for(root)

        result = run(root)

        assert result.returncode == 1
        assert "apps/web is marked (planned) and exists" in result.stderr

    def test_a_planned_path_that_is_absent_passes(self, repo):
        root = repo(web_note="(planned)", build_web=False)
        _checker_for(root)

        assert run(root).returncode == 0

    def test_a_tree_that_matches_passes(self, repo):
        root = repo()
        _checker_for(root)

        assert run(root).returncode == 0


class TestADerivedNumber:
    def test_a_number_that_stopped_being_true_fails(self, repo):
        root = repo(extra={
            "docs/claim.md": "it is 3 lines <!-- derived: lines docs/target.md -->\n",
            "docs/target.md": "one\ntwo\n",
        })
        _checker_for(root)

        result = run(root)

        assert result.returncode == 1
        assert "says 3, but lines docs/target.md is 2" in result.stderr

    def test_a_number_that_is_true_passes(self, repo):
        root = repo(extra={
            "docs/claim.md": "it is 2 lines <!-- derived: lines docs/target.md -->\n",
            "docs/target.md": "one\ntwo\n",
        })
        _checker_for(root)

        assert run(root).returncode == 0

    def test_a_count_derivation(self, repo):
        root = repo(extra={
            "docs/claim.md": "3 of them <!-- derived: count docs/d/*.md -->\n",
            "docs/d/a.md": "", "docs/d/b.md": "",
        })
        _checker_for(root)

        result = run(root)

        assert result.returncode == 1
        assert "count docs/d/*.md is 2" in result.stderr

    def test_an_unmarked_number_is_not_reported(self, repo):
        """The false-positive case, and the one that decides whether this gate
        survives. This repository's prose is full of real numbers that derive
        from nothing in it — five rubric dimensions, six night stages — and a
        checker that guessed at them would be wrong often enough to be turned
        off."""
        root = repo(extra={
            "docs/claim.md": "There are 5 rubric dimensions and 6 night stages.\n"
                             "The file is 900 lines long. 14 ADRs.\n",
        })
        _checker_for(root)

        result = run(root)

        assert result.returncode == 0, result.stderr
        assert "900" not in result.stderr and "900" not in result.stdout

    def test_a_matches_derivation_counts_inside_a_file(self, repo):
        """The shape the stale claims took most often: a count of things inside
        a file, which no glob can reach. Adding the drift gate itself made ten
        documents say "ten gates"."""
        root = repo(extra={
            "docs/claim.md": '3 rows <!-- derived: matches docs/t.py ^    \\(" -->\n',
            "docs/t.py": '    ("a", 1),\n    ("b", 2),\n',
        })
        _checker_for(root)

        result = run(root)

        assert result.returncode == 1
        assert "is 2" in result.stderr

    def test_the_number_taken_is_the_one_nearest_the_marker(self, repo):
        """`python3 scripts/gate.py runs 11 gates <!-- ... -->` reported the
        **3** in `python3`, on the first real line this was pointed at. The gap
        between the number and its marker carries no digits."""
        root = repo(extra={
            "docs/claim.md":
                "`python3 x.py` runs 2 lines <!-- derived: lines docs/target.md -->\n",
            "docs/target.md": "one\ntwo\n",
        })
        _checker_for(root)

        result = run(root)

        assert result.returncode == 0, result.stderr

    def test_a_derivation_that_cannot_be_computed_is_reported(self, repo):
        """Not silently skipped. A marker pointing at a moved file is a claim
        nobody is checking any more, which is the state this exists to end."""
        root = repo(extra={
            "docs/claim.md": "it is 2 lines <!-- derived: lines docs/gone.md -->\n",
        })
        _checker_for(root)

        result = run(root)

        assert result.returncode == 1
        assert "cannot derive lines docs/gone.md" in result.stderr


class TestTheBookkeeping:
    def test_an_in_flight_change_with_no_open_task_fails(self, repo):
        """`nebius-executor` read "✓ Complete" for three weeks with none of the
        work done, because its second task group was prose rather than tasks."""
        root = repo(extra={
            "openspec/changes/2026-01-01-a-change/tasks.md": "# Tasks\n\n- [x] 1.1 done\n",
        })
        _checker_for(root)

        result = run(root)

        assert result.returncode == 1
        assert "no unchecked task" in result.stderr

    def test_an_in_flight_change_with_an_open_task_passes(self, repo):
        root = repo(extra={
            "openspec/changes/2026-01-01-a-change/tasks.md":
                "# Tasks\n\n- [x] 1.1 done\n- [ ] 1.2 not\n",
        })
        _checker_for(root)

        assert run(root).returncode == 0

    def test_a_change_with_no_tasks_file_fails(self, repo):
        root = repo(extra={"openspec/changes/2026-01-01-a-change/proposal.md": "# A\n"})
        _checker_for(root)

        result = run(root)

        assert result.returncode == 1
        assert "no tasks.md" in result.stderr

    def test_a_spec_with_no_archived_change_fails(self, repo):
        """A requirement in force while its proposal is still open."""
        root = repo(extra={"openspec/specs/orphan/spec.md": "# orphan\n"})
        _checker_for(root)

        result = run(root)

        assert result.returncode == 1
        assert "no archived change that added them" in result.stderr

    def test_a_spec_with_its_archived_change_passes(self, repo):
        root = repo(extra={
            "openspec/specs/real/spec.md": "# real\n",
            "openspec/changes/archive/2026-01-01-add-real/specs/real/spec.md": "# real\n",
        })
        _checker_for(root)

        assert run(root).returncode == 0


class TestItDoesNotOverstateItself:
    def test_a_passing_run_says_what_it_checked(self, repo):
        root = repo()
        _checker_for(root)

        out = run(root).stdout

        assert "the documented tree" in out
        assert "says what it derives from" in out
        assert "bookkeeping" in out

    def test_a_passing_run_says_what_it_did_not_check(self, repo):
        """A narrow check that passes is read as a broad one unless it says
        otherwise, and the drift this misses is the drift somebody still has to
        go and look for."""
        root = repo()
        _checker_for(root)

        out = run(root).stdout

        assert "Not checked" in out
        assert "still need somebody to read them" in out


def test_this_repository_passes_its_own_check():
    """The gate runs this; so does CI. Here so a failure is attributed to the
    claim that broke rather than to a gate row somebody has to go and read."""
    result = subprocess.run(
        [sys.executable, str(CHECKER)], cwd=REPO_ROOT, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr
