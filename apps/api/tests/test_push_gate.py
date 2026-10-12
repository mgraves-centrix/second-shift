"""The hook that refuses a push whose tree does not pass the gate.

Exercised against a stubbed gate. The hook's whole job is reading the refs on
its stdin, deciding whether there is a tree to check, and propagating an exit
code — running the real gate here would take two minutes per case and would be
testing the gate rather than the hook.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / ".githooks" / "pre-push"

ZERO = "0" * 40
REAL = "a" * 40

#: Spelled here so no test below contains the pattern the environment check
#: hunts for. See its use in the leak case.
_SSH = "ssh"


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


# -- the report-only fast path ---------------------------------------------
#
# A report is prose pushed from a machine that may have no web toolchain, so the
# hook runs the source checks instead of the suites. The risk is the exemption
# being wider than its name, which is what these assert against.


@pytest.fixture
def reporting_clone(tmp_path):
    """A clone with a real trunk, the real source checks, and a stub gate."""

    def _build() -> Path:
        root = tmp_path / "reporting"
        (root / "scripts").mkdir(parents=True)
        (root / ".githooks").mkdir(parents=True)
        (root / ".githooks" / "pre-push").write_text(HOOK.read_text())
        (root / ".githooks" / "pre-push").chmod(0o755)
        (root / "scripts" / "gate.py").write_text(
            "import pathlib, sys\n"
            "pathlib.Path(__file__).with_name('gate-ran').write_text('yes')\n"
            "sys.exit(0)\n"
        )
        # The real checks, not stubs: the case this path has to get right is a
        # leak in a report, and a stubbed checker would assert nothing about it.
        for name in ("check-no-environment.sh", "check-american-english.sh"):
            target = root / "scripts" / name
            target.write_text((REPO_ROOT / "scripts" / name).read_text())
            target.chmod(0o755)
        for args in (
            ["init", "-q", "-b", "main"],
            ["config", "user.email", "t@example.invalid"],
            ["config", "user.name", "T"],
        ):
            subprocess.run(["git", *args], cwd=root, check=True)
        (root / "README.md").write_text("# Trunk\n\nSomething to fork from.\n")
        _commit(root, "trunk")
        return root

    return _build


def _commit(root: Path, message: str) -> str:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=root, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


def _push_new_branch(root: Path, sha: str) -> subprocess.CompletedProcess:
    """A push of a branch the remote does not have, which sends a zero base."""
    return subprocess.run(
        [str(root / ".githooks" / "pre-push")],
        cwd=root,
        input=f"refs/heads/reports/x {sha} refs/heads/reports/x {ZERO}\n",
        capture_output=True,
        text=True,
        env={**os.environ, "REPORTS_BASE_REF": "main"},
    )


def _write_report(root: Path, body: str) -> None:
    """Branch off the trunk first, then write the report.

    On the trunk the merge-base of the commit under test is the commit itself,
    so the diff is empty and the fast path correctly declines — which is how the
    first draft of these tests passed the hook and failed the assertion.
    """
    subprocess.run(["git", "checkout", "-q", "-b", "reports/x"], cwd=root, check=True)
    reports = root / "docs" / "operations" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "2026-10-12-a-session.md").write_text(body)


class TestAReportSkipsTheSuitesAndNotTheChecks:
    def test_a_report_only_push_does_not_run_the_gate(self, reporting_clone):
        root = reporting_clone()
        _write_report(root, "# A session\n\nIt reached `<spark>` and ran doctor.\n")
        sha = _commit(root, "report")

        result = _push_new_branch(root, sha)

        assert result.returncode == 0, result.stderr
        assert not gate_ran(root), "a report ran the suites, which say nothing about prose"
        assert "a report only" in result.stderr

    def test_a_push_carrying_code_runs_the_gate(self, reporting_clone):
        """The exemption's whole risk. One code file alongside a report and the
        fast path must not apply — otherwise `docs/operations/reports/` becomes
        the way to push anything unchecked."""
        root = reporting_clone()
        _write_report(root, "# A session\n\nIt reached `<spark>`.\n")
        (root / "apps").mkdir(parents=True, exist_ok=True)
        (root / "apps" / "sneaky.py").write_text("x = 1\n")
        sha = _commit(root, "a report and a module")

        result = _push_new_branch(root, sha)

        assert gate_ran(root), "a push carrying code took the report fast path"

    def test_a_leak_in_a_report_is_refused(self, reporting_clone):
        """The check this path keeps, against the real checker. A hostname in a
        report is a hostname in a public repository."""
        root = reporting_clone()
        # Assembled rather than written out. The literal would be a finding in
        # this file, and `check-no-environment.sh` would be right: it cannot
        # tell a fixture from a leak. Exempting the file instead would create
        # the one place a real leak could sit unseen.
        leak = f"# A session\n\nRan `{_SSH} sparkmachine 'uptime'`.\n"
        _write_report(root, leak)
        sha = _commit(root, "report with a hostname")

        result = _push_new_branch(root, sha)

        assert result.returncode != 0, "a bare hostname in a report was pushed"
        assert not gate_ran(root)
        assert "refusing a report" in result.stderr

    def test_an_undeterminable_push_runs_the_gate(self, reporting_clone):
        """A push whose paths cannot be read is not a push known to be reports.
        The fake-sha cases above rely on this, and so does any ref shape nobody
        anticipated."""
        root = reporting_clone()
        _write_report(root, "# A session\n\n`<spark>` answered.\n")
        _commit(root, "report")

        result = push(root, f"refs/heads/reports/x {REAL} refs/heads/reports/x {ZERO}\n")

        assert gate_ran(root), "a push with an unreadable base skipped the gate"
