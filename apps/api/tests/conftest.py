from __future__ import annotations

import pytest

from secondshift.db import connection, migrate
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
    return repo.insert_agent(
        name="researcher",
        role="researcher",
        version=1,
        prompt_path="agents/prompts/researcher.v1.md",
        prompt_sha="deadbeef",
    )


@pytest.fixture
def run_id(repo) -> str:
    entry = repo.insert_entry(
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
