"""The deploy script's rubric guard.

`deploy.sh` replaces the target tree with `rm -rf`. The rubric is the one file it
carries whose content hash is recorded in the database, so a rubric edited only on
the target is destroyed by a routine deploy — silently changing the rubric under a
pinned baseline. That is not a hypothetical: it is the likeliest explanation for a
machine reporting a rubric hash no commit has ever produced.

Exercised with `ssh` and `npm` stubbed on PATH, so the guard's decision is tested
without a target host. What happens after the guard is not this file's business —
the build marker is the boundary.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DEPLOY = REPO_ROOT / "deploy" / "spark" / "deploy.sh"
RUBRIC = REPO_ROOT / "config" / "evals" / "rubric.md"

_SSH_STUB = """#!/usr/bin/env bash
# Only the rubric probe asks a question; everything else is a transfer.
if [[ "$*" == *"echo absent"* ]]; then
    printf '%s\\n' "${STUB_REMOTE_RUBRIC_SHA}"
    exit 0
fi
cat >/dev/null 2>&1 || true
exit 0
"""

_NPM_STUB = """#!/usr/bin/env bash
# Reaching the build means the guard let the deploy through.
touch "${STUB_BUILD_MARKER}"
exit 0
"""


@pytest.fixture
def deploy(tmp_path):
    """Run the deploy script against stubbed ssh and npm."""
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    for name, body in (("ssh", _SSH_STUB), ("npm", _NPM_STUB)):
        path = stub_bin / name
        path.write_text(body)
        path.chmod(0o755)
    marker = tmp_path / "built"

    def _run(remote_sha: str, *, override: bool = False):
        env = dict(os.environ)
        env.pop("SECOND_SHIFT_RUBRIC_OVERWRITE", None)
        env.update(
            PATH=f"{stub_bin}{os.pathsep}{env['PATH']}",
            SPARK_HOST="target.example.invalid",
            SPARK_USER="deployer",
            SPARK_PATH=str(tmp_path / "target"),
            STUB_REMOTE_RUBRIC_SHA=remote_sha,
            STUB_BUILD_MARKER=str(marker),
        )
        if override:
            env["SECOND_SHIFT_RUBRIC_OVERWRITE"] = "1"
        completed = subprocess.run(
            ["bash", str(DEPLOY)],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        return completed, marker.exists()

    return _run


def _shipped_sha() -> str:
    return hashlib.sha256(RUBRIC.read_bytes()).hexdigest()


def test_a_differing_rubric_on_the_target_stops_the_deploy(deploy):
    completed, built = deploy("0" * 64)

    assert completed.returncode == 1
    assert "refusing to deploy" in completed.stderr
    # Nothing was built, so nothing was shipped and nothing was deleted. The
    # refusal has to land before the transfer or it lands after the rm -rf.
    assert not built


def test_the_refusal_names_both_hashes_and_how_to_recover_the_file(deploy):
    completed, _ = deploy("0" * 64)

    assert "0" * 12 in completed.stderr
    assert _shipped_sha()[:12] in completed.stderr
    assert "scp" in completed.stderr
    assert "secondshift.evals status" in completed.stderr
    assert "SECOND_SHIFT_RUBRIC_OVERWRITE=1" in completed.stderr


def test_a_target_with_no_rubric_deploys(deploy):
    """A first deploy has nothing to destroy."""
    completed, built = deploy("absent")

    assert "refusing to deploy" not in completed.stderr
    assert built


def test_a_matching_rubric_deploys_without_comment(deploy):
    completed, built = deploy(_shipped_sha())

    assert "refusing to deploy" not in completed.stderr
    assert "override set" not in completed.stdout
    assert built


def test_the_override_proceeds_and_says_what_it_replaces(deploy):
    completed, built = deploy("0" * 64, override=True)

    assert "refusing to deploy" not in completed.stderr
    assert "override set" in completed.stdout
    assert "0" * 12 in completed.stdout
    assert _shipped_sha()[:12] in completed.stdout
    assert built
