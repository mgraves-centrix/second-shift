"""The systemd units, checked against the configuration they must agree with.

A unit is not executable from a test, but the two things most likely to be wrong
about this one are: the port it publishes, and the name the server reports for
itself. Both are agreements with `config/models.toml`, and both fail silently —
a port mismatch makes the probe report the reasoner unreachable while it is
running, and a name mismatch makes the probe refuse a server that is serving the
right model.

Spike B served on 8000 while the configuration allocated 8200, so this is a
disagreement that has already happened once.
"""

from __future__ import annotations

import configparser
from pathlib import Path

import pytest

from secondshift import config

REPO_ROOT = Path(__file__).resolve().parents[3]
UNITS = REPO_ROOT / "deploy" / "spark"
REASONER_UNITS = (
    UNITS / "second-shift-reasoner.service",
    UNITS / "second-shift-reasoner.user.service",
)


def _service(path: Path) -> dict[str, str]:
    """The `[Service]` section.

    Interpolation off: systemd's `%h` is a specifier, and configparser would
    read it as a broken substitution. Non-strict because systemd permits a key
    more than once.
    """
    parser = configparser.RawConfigParser(strict=False)
    parser.optionxform = str
    parser.read_string(path.read_text())
    return dict(parser["Service"])


@pytest.mark.parametrize("unit", REASONER_UNITS, ids=lambda p: p.name)
class TestTheReasonerUnit:
    def test_it_parses(self, unit):
        assert _service(unit)["ExecStart"]

    def test_it_publishes_the_port_the_probe_checks(self, unit):
        """A unit on another port leaves the probe reporting an unreachable
        server that is in fact running."""
        expected = config.local_reasoner_settings().port
        assert f":{expected}:" in _service(unit)["ExecStart"]

    def test_it_serves_the_name_the_probe_expects(self, unit):
        """The probe refuses an endpoint serving anything but this name."""
        served = config.expected_local_model()
        assert f"--served-model-name {served}" in _service(unit)["ExecStart"]

    def test_it_restarts_when_the_server_exits(self, unit):
        assert _service(unit)["Restart"] == "always"

    def test_it_allows_the_model_time_to_load(self, unit):
        """Roughly three minutes from a warm cache, and a cold one pulls first.
        A start timeout shorter than the load is a boot loop."""
        assert int(_service(unit)["TimeoutStartSec"]) >= 600

    def test_it_keeps_the_spike_s_memory_ceiling(self, unit):
        """0.85 leaves 9 of 121 GiB and no room for ASR or the embedder, which
        was the whole argument for NVFP4."""
        assert "--gpu-memory-utilization 0.30" in _service(unit)["ExecStart"]

    def test_it_does_not_carry_the_published_recipe_s_broken_flags(self, unit):
        """--moe-backend marlin is refused for this checkpoint, and
        num_speculative_tokens alone is rejected without a method."""
        exec_start = _service(unit)["ExecStart"]
        assert "--moe-backend" not in exec_start
        assert '"method":"mtp"' in exec_start


class TestTheEmbedderUnit:
    """The flags here were wrong when this unit was first written.

    It shipped `--task embed`, which vLLM 0.27.1 rejects outright — the
    container exits before loading anything. Only running it on the machine
    found that, which is the argument for these checks: a unit file is prose
    until something executes it, and the suite is the cheapest place to notice
    a flag that no longer exists.
    """

    @pytest.fixture
    def unit(self) -> Path:
        return UNITS / "second-shift-embedder.service"

    def test_it_parses(self, unit):
        assert _service(unit)["ExecStart"]

    def test_it_publishes_the_configured_port(self, unit):
        settings = config.local_embedder_settings()
        assert f":{settings.port}:8000" in _service(unit)["ExecStart"]

    def test_it_serves_the_configured_name(self, unit):
        settings = config.local_embedder_settings()
        assert f"--served-model-name {settings.model}" in _service(unit)["ExecStart"]

    def test_it_does_not_use_the_flag_vllm_removed(self, unit):
        """`--task` is not a vLLM 0.27.1 argument. `--runner` replaced it."""
        exec_start = _service(unit)["ExecStart"]
        assert "--task" not in exec_start
        assert "--runner pooling" in exec_start

    def test_it_carries_the_flag_the_checkpoint_requires(self, unit):
        """This model will not load without it, and that is worth stating.

        `--trust-remote-code` runs code from the model repository. It is here
        deliberately, not by accident, and a test naming it means removing it
        is also deliberate.
        """
        assert "--trust-remote-code" in _service(unit)["ExecStart"]

    def test_it_does_not_claim_the_reasoner_s_port(self, unit):
        reasoner_port = config.local_reasoner_settings().port
        assert f":{reasoner_port}:" not in _service(unit)["ExecStart"]


def test_the_units_are_installable():
    """Each names where it is wanted, or `systemctl enable` has nothing to do."""
    for unit in REASONER_UNITS:
        parser = configparser.RawConfigParser(strict=False)
        parser.read_string(unit.read_text())
        assert parser["Install"]["WantedBy"]
