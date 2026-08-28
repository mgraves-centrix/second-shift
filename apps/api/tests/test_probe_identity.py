"""The probe must verify what answers, not merely that something does.

On 2026-08-27 the Spark was serving a different model entirely on the port the
probe treats as the local reasoner. Reachability-only reported it available, and
a local-only idea would have been routed to it.
"""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from secondshift.airlock.capability import build_report
from secondshift.airlock.policy import Policy
from secondshift.config import (
    CUDA,
    LOCAL_REASONER,
    SPEECH_STACK,
    Capability,
    ProbeResult,
    Profile,
    _check_endpoint,
    resolve_profile,
)

EXPECTED = "nemotron-3.5-lightning"


class _ModelServer(BaseHTTPRequestHandler):
    served: list[str] = []
    malformed = False

    def do_GET(self):
        if self.malformed:
            body = b"<html>not json</html>"
        else:
            body = json.dumps(
                {"object": "list", "data": [{"id": m} for m in self.served]}
            ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep pytest output clean
        pass


@pytest.fixture
def model_endpoint():
    """A stub OpenAI-compatible /v1/models endpoint."""
    servers = []

    def _start(served: list[str], malformed: bool = False) -> int:
        handler = type(
            "H", (_ModelServer,), {"served": served, "malformed": malformed}
        )
        httpd = HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        servers.append(httpd)
        return httpd.server_address[1]

    yield _start
    for httpd in servers:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture
def silent_socket():
    """A socket that accepts a connection and then says nothing."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    yield listener.getsockname()[1]
    listener.close()


class TestEndpointIdentity:
    def test_expected_model_is_available(self, model_endpoint):
        port = model_endpoint([EXPECTED])
        result = _check_endpoint("127.0.0.1", port, EXPECTED)
        assert result.available is True
        assert EXPECTED in result.detail

    def test_different_model_is_refused_by_name(self, model_endpoint):
        """The Qwen case, exactly."""
        port = model_endpoint(["qwen3.8-27b"])
        result = _check_endpoint("127.0.0.1", port, EXPECTED)
        assert result.available is False
        assert "qwen3.8-27b" in result.detail
        assert EXPECTED in result.detail

    def test_expected_among_several_served_models(self, model_endpoint):
        port = model_endpoint(["something-else", EXPECTED])
        assert _check_endpoint("127.0.0.1", port, EXPECTED).available is True

    def test_connectable_but_silent_is_unavailable(self, silent_socket):
        result = _check_endpoint(
            "127.0.0.1", silent_socket, EXPECTED, identity_timeout=0.4
        )
        assert result.available is False
        assert "does not identify" in result.detail

    def test_malformed_response_does_not_raise(self, model_endpoint):
        port = model_endpoint([], malformed=True)
        result = _check_endpoint("127.0.0.1", port, EXPECTED)
        assert result.available is False

    def test_no_expected_model_configured_cannot_verify(self, model_endpoint):
        port = model_endpoint([EXPECTED])
        result = _check_endpoint("127.0.0.1", port, expected_model="")
        assert result.available is False
        assert "cannot be verified" in result.detail

    def test_unreachable_behaves_as_before(self):
        result = _check_endpoint("127.0.0.1", 59999, EXPECTED)
        assert result.available is False
        assert "unreachable" in result.detail


class TestDownstreamOfIdentity:
    def _probe_with(self, endpoint: Capability) -> ProbeResult:
        return ProbeResult(
            {
                CUDA: Capability(CUDA, True, "nvidia-smi present"),
                LOCAL_REASONER: endpoint,
                SPEECH_STACK: Capability(SPEECH_STACK, True, "importable"),
            }
        )

    def test_wrong_model_degrades_to_cloud(self, model_endpoint):
        port = model_endpoint(["qwen3.8-27b"])
        probe = self._probe_with(_check_endpoint("127.0.0.1", port, EXPECTED))
        resolved = resolve_profile(env={}, probe_result=probe)
        assert resolved.profile is Profile.CLOUD
        assert resolved.degraded is True

    def test_wrong_model_makes_local_only_unavailable_by_name(self, model_endpoint):
        port = model_endpoint(["qwen3.8-27b"])
        probe = self._probe_with(_check_endpoint("127.0.0.1", port, EXPECTED))
        report = build_report(resolve_profile(env={}, probe_result=probe))
        assert report.is_available(Policy.LOCAL_ONLY) is False
        assert "qwen3.8-27b" in (report.reason_for(Policy.LOCAL_ONLY) or "")

    def test_identity_failure_never_aborts_startup(self, model_endpoint):
        """Degrades exactly as an unreachable endpoint does."""
        port = model_endpoint(["qwen3.8-27b"])
        probe = self._probe_with(_check_endpoint("127.0.0.1", port, EXPECTED))
        assert resolve_profile(env={}, probe_result=probe).profile is Profile.CLOUD

    def test_expected_model_still_resolves_to_spark(self, model_endpoint):
        port = model_endpoint([EXPECTED])
        probe = self._probe_with(_check_endpoint("127.0.0.1", port, EXPECTED))
        resolved = resolve_profile(env={}, probe_result=probe)
        assert resolved.profile is Profile.SPARK
        assert build_report(resolved).is_available(Policy.LOCAL_ONLY) is True


class TestEndpointConfiguration:
    """The endpoint is configuration. A config nothing reads only looks configured."""

    def test_port_comes_from_configuration_not_a_literal(self, tmp_path, monkeypatch):
        from secondshift import config

        cfg = tmp_path / "models.toml"
        cfg.write_text(
            '[local]\nreasoner_model = "m"\nreasoner_host = "192.0.2.10"\n'
            "reasoner_port = 9999\n"
        )
        monkeypatch.setattr(config, "_MODELS_CONFIG", cfg)
        assert config.local_endpoint() == ("192.0.2.10", 9999)

    def test_environment_overrides_the_file(self, tmp_path, monkeypatch):
        from secondshift import config

        cfg = tmp_path / "models.toml"
        cfg.write_text('[local]\nreasoner_port = 9999\n')
        monkeypatch.setattr(config, "_MODELS_CONFIG", cfg)
        monkeypatch.setenv(config.ENV_LOCAL_PORT, "7777")
        assert config.local_endpoint()[1] == 7777

    def test_probe_uses_the_configured_endpoint(self, tmp_path, monkeypatch, model_endpoint):
        from secondshift import config

        port = model_endpoint([EXPECTED])
        cfg = tmp_path / "models.toml"
        cfg.write_text(
            f'[local]\nreasoner_model = "{EXPECTED}"\n'
            f'reasoner_host = "127.0.0.1"\nreasoner_port = {port}\n'
        )
        monkeypatch.setattr(config, "_MODELS_CONFIG", cfg)
        result = config.probe(speech_module="definitely_not_installed")
        assert result.available(LOCAL_REASONER) is True

    def test_missing_config_falls_back_without_raising(self, tmp_path, monkeypatch):
        from secondshift import config

        monkeypatch.setattr(config, "_MODELS_CONFIG", tmp_path / "absent.toml")
        assert config.local_endpoint() == ("127.0.0.1", 8000)
        assert config.expected_local_model() == ""
