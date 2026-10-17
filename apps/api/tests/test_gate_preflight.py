"""The gate's own preflight: a tool at the wrong version is a missing tool.

CI installs `@fission-ai/openspec@1.11.0`; the gate called whatever `openspec`
was on PATH. On 17 Oct a laptop with 1.14.1 failed the specs gate on `main`,
because 1.14 treats requirement text over 500 characters as a strict failure
and nine of this repository's twenty-five specs and changes have some. Nothing
in the tree had changed. A gate that answers differently on two machines for
the same tree is two gates.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def gate(monkeypatch):
    def _load():
        spec = importlib.util.spec_from_file_location("gate_under_test", ROOT / "scripts" / "gate.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    return _load


def test_the_pin_is_the_version_ci_installs_and_the_bootstrap_names(gate):
    pinned = gate().OPENSPEC_VERSION
    workflow = (ROOT / ".github" / "workflows" / "gate.yml").read_text()
    bootstrap = (ROOT / "docs" / "development" / "GATES.md").read_text()

    assert re.findall(r"@fission-ai/openspec@([\d.]+)", workflow) == [pinned]
    assert f"@fission-ai/openspec@{pinned}" in bootstrap


def test_another_version_is_refused_by_name(gate, monkeypatch):
    module = gate()
    monkeypatch.setattr(module, "_openspec_version", lambda: "1.14.1")
    monkeypatch.setattr(module.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(module.Path, "exists", lambda self: True)
    monkeypatch.setattr(module.Path, "is_dir", lambda self: True)

    reason = module.preflight()

    assert reason is not None
    assert "1.14.1" in reason and module.OPENSPEC_VERSION in reason
    assert "GATE_OPENSPEC" in reason


def test_the_pinned_version_passes_preflight(gate, monkeypatch):
    module = gate()
    monkeypatch.setattr(module, "_openspec_version", lambda: module.OPENSPEC_VERSION)
    monkeypatch.setattr(module.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(module.Path, "exists", lambda self: True)
    monkeypatch.setattr(module.Path, "is_dir", lambda self: True)

    assert module.preflight() is None


def test_gate_openspec_chooses_the_binary(gate, monkeypatch):
    """The same escape hatch as GATE_PYTHON and GATE_CHROME, so a machine
    whose global CLI is newer can run the gate without replacing it."""
    monkeypatch.setenv("GATE_OPENSPEC", "/opt/pinned/openspec")

    specs = dict(gate().GATES)["specs"]

    assert specs[0] == "/opt/pinned/openspec"
