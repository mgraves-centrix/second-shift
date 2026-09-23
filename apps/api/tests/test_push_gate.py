"""The hook that refuses a push whose tree does not pass the gate.

Exercised against a stubbed gate. The hook's whole job is reading the refs on
its stdin, deciding whether there is a tree to check, and propagating an exit
code — running the real gate here would take two minutes per case and would be
testing the gate rather than the hook.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / ".githooks" / "pre-push"

ZERO = "0" * 40
REAL = "a" * 40


@pytest.fixture
def clone(tmp_path):
    """A repository with the real hook and a gate that answers as told."""

    def _build(gate_exit: int) -> Path:
        root = tmp_path / "clone"
        (root / "scripts").mkdir(parents=True)
        (root / ".githooks").mkdir(parents=True)
        (root / ".githooks" / "pre-push").write_text(HOOK.read_text())
        (root / ".githooks" / "pre-push").chmod(0o755)
        (root / "scripts" / "gate.py").write_text(
            "import pathlib, sys\n"
            "pathlib.Path(__file__).with_name('gate-ran').write_text('yes')\n"
            f"sys.exit({gate_exit})\n"
        )
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
        return root

    return _build


def push(root: Path, refs: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(root / ".githooks" / "pre-push")],
        cwd=root,
        input=refs,
        capture_output=True,
        text=True,
    )


def gate_ran(root: Path) -> bool:
    return (root / "scripts" / "gate-ran").exists()


class TestThePushGate:
    def test_a_red_gate_refuses_the_push(self, clone):
        root = clone(gate_exit=1)

        result = push(root, f"refs/heads/main {REAL} refs/heads/main {ZERO}\n")

        assert result.returncode == 1
        assert gate_ran(root)

    def test_the_refusal_names_the_way_through(self, clone):
        """An override somebody cannot find is one they route around by
        disabling the hook entirely."""
        root = clone(gate_exit=1)

        result = push(root, f"refs/heads/main {REAL} refs/heads/main {ZERO}\n")

        assert "--no-verify" in result.stderr

    def test_the_refusal_names_why_it_exists(self):
        """Two red commits in three days, both from an exit status that never
        reached the shell. The message says so, because a guard whose reason is
        invisible reads as ceremony."""
        text = HOOK.read_text()

        assert "| tail -2" in text
        assert "> log 2>&1;" in text

    def test_a_green_gate_lets_the_push_through(self, clone):
        root = clone(gate_exit=0)

        result = push(root, f"refs/heads/main {REAL} refs/heads/main {ZERO}\n")

        assert result.returncode == 0
        assert gate_ran(root)

    def test_a_deletion_is_not_gated(self, clone):
        """`git push --delete` sends an all-zero local hash. There is no tree to
        check, and a two-minute wait to remove a branch is the friction that
        gets a hook uninstalled."""
        root = clone(gate_exit=1)

        result = push(root, f"(delete) {ZERO} refs/heads/gone {REAL}\n")

        assert result.returncode == 0
        assert not gate_ran(root), "the gate ran for a push with nothing to check"

    def test_a_deletion_alongside_a_real_push_is_gated(self, clone):
        """One ref with a tree is enough. The cheap reading — 'any zero hash
        means skip' — would let a red commit through behind a branch deletion."""
        root = clone(gate_exit=1)

        result = push(
            root,
            f"(delete) {ZERO} refs/heads/gone {REAL}\n"
            f"refs/heads/main {REAL} refs/heads/main {ZERO}\n",
        )

        assert result.returncode == 1
        assert gate_ran(root)


def test_the_hook_is_executable():
    """Tracked with its mode, or `core.hooksPath` points at a file git skips."""
    assert HOOK.stat().st_mode & 0o111, f"{HOOK} is not executable"
