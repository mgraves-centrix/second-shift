from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from secondshift import config
from secondshift.db import connection, migrate
from secondshift.db.connection import now_ms
from secondshift.db.repository import Repository
from secondshift.telemetry.pricing import PricingTable, Rate
from secondshift.telemetry.recorder import Recorder


@pytest.fixture
def db(tmp_path):
    """Open connections that are guaranteed to be closed at teardown.

    An unclosed sqlite3 connection raises during interpreter finalization, and
    `filterwarnings = ["error"]` correctly turns that into a failure.
    """
    opened = []

    def _open(name: str = "second-shift.db"):
        c = connection.connect(tmp_path / name)
        opened.append(c)
        return c

    yield _open
    for c in opened:
        c.close()


@pytest.fixture
def conn(tmp_path):
    c = connection.connect(tmp_path / "second-shift.db")
    migrate.migrate(c)
    yield c
    c.close()


@pytest.fixture
def repo(conn) -> Repository:
    return Repository(conn)


@pytest.fixture
def agent_id(repo) -> str:
    """The researcher, registered against its real prompt file.

    This fixture wrote `prompt_sha="deadbeef"` against a path that did not
    exist until `agents` shipped — which meant the column that exists to prove
    an eight-week curve measures the brain rather than an edited prompt was
    provably measuring nothing. Registering for real means every test that
    records an invocation records a hash of text that is actually on disk.
    """
    from secondshift.agents.roster import register

    return register(repo)["researcher"]


@pytest.fixture
def run_id(repo) -> str:
    entry = repo.insert_entry(
        created_at_ms=now_ms(),
        captured_tz="America/Los_Angeles",
        tz_offset_min=-420,
        modality="text",
        default_policy="cloud-assisted",
        status="queued",
        capture_profile="spark",
        raw_text="an idea",
    )
    return repo.insert_run(
        entry_id=entry,
        night_of="2026-08-27",
        effective_policy="cloud-assisted",
        policy_source="entry-default",
        compute_profile="spark",
    )


@pytest.fixture
def pricing() -> PricingTable:
    """A deterministic table: free local, priced cloud, nothing else."""
    return PricingTable(
        [
            Rate("local-vllm", "*", 0, 0.0, 0.0),
            Rate("token-factory", "nemotron-3-super", 0, 1.0, 3.0),
        ]
    )


@pytest.fixture
def recorder(repo, pricing) -> Recorder:
    return Recorder(repo, pricing=pricing, compute_profile="spark")


# -- a stand-in for the local inference server -----------------------------


class VllmStub:
    """An OpenAI-compatible endpoint on a real socket.

    A real server rather than a patched transport: the provider's job is almost
    entirely reading what comes back over HTTP, and a test that replaces the
    transport would exercise everything except the part that can be wrong.
    """

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.status = 200
        self.body: object = None
        self.raw: bytes | None = None
        self.delay_s = 0.0
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # -- lifecycle -----------------------------------------------------

    def start(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
        self._server.stub = self  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    @property
    def host(self) -> str:
        assert self._server is not None
        return self._server.server_address[0]

    @property
    def port(self) -> int:
        assert self._server is not None
        return int(self._server.server_address[1])

    # -- what it answers with -------------------------------------------

    def answers(
        self,
        text: str = "an answer",
        *,
        prompt_tokens: int = 11,
        completion_tokens: int = 7,
        reasoning_tokens: int | None = None,
        finish_reason: str = "stop",
        reasoning_content: str | None = None,
    ) -> VllmStub:
        message: dict = {"role": "assistant", "content": text}
        if reasoning_content is not None:
            message["reasoning_content"] = reasoning_content
        usage: dict = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
        if reasoning_tokens is not None:
            usage["completion_tokens_details"] = {"reasoning_tokens": reasoning_tokens}
        self.status = 200
        self.raw = None
        self.body = {
            "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
            "usage": usage,
        }
        return self

    def fails(self, status: int, detail: str) -> VllmStub:
        self.status = status
        self.body = None
        self.raw = detail.encode()
        return self

    def answers_with(self, raw: bytes) -> VllmStub:
        self.status = 200
        self.body = None
        self.raw = raw
        return self


class _StubHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:  # noqa: N802 - the name http.server dispatches on
        stub: VllmStub = self.server.stub  # type: ignore[attr-defined]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            stub.requests.append(json.loads(raw))
        except ValueError:
            stub.requests.append({})
        if stub.delay_s:
            time.sleep(stub.delay_s)
        payload = stub.raw if stub.raw is not None else json.dumps(stub.body).encode()
        self.send_response(stub.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args) -> None:
        """Silent. A test suite is not a request log."""


@pytest.fixture
def vllm_stub():
    """A running stub server, stopped at teardown."""
    stub = VllmStub().answers()
    stub.start()
    yield stub
    stub.stop()


@pytest.fixture
def local_reasoner_env(vllm_stub, monkeypatch):
    """Point the configured local endpoint at the stub.

    Uses the same environment variables an operator would, rather than a test
    seam: `config.local_endpoint()` already reads them, so this exercises the
    real resolution path.
    """
    monkeypatch.setenv(config.ENV_LOCAL_HOST, vllm_stub.host)
    monkeypatch.setenv(config.ENV_LOCAL_PORT, str(vllm_stub.port))
    monkeypatch.setenv(config.ENV_LOCAL_MODEL, "stub-served-model")
    return vllm_stub
