"""The check that a judge package carries nothing it must not.

`model_call_payloads` is how raw, unredacted content for local-only ideas is
reached, and the schema has said since day one that it "must never be synced,
uploaded, or included in a judge deployment". That was a SQL comment with
nothing behind it.

The rows hold `prompt_path` and `completion_path` rather than the text itself —
the content lives under `data/payloads/`. Refusing the rows is still worth
doing: they are an index of what the subject thought about and when.

The judge image bakes a database in, which is the one path where this goes
wrong: build against the wrong file and the subject's unredacted thinking ships
to a public endpoint.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from secondshift.db import migrate
from secondshift.db.connection import now_ms
from secondshift.db.repository import Repository

CHECK = Path(__file__).resolve().parents[3] / "scripts" / "check-judge-package.py"


def _run(path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECK), str(path)],
        capture_output=True,
        text=True,
    )


@pytest.fixture
def seeded(db, tmp_path):
    """A database as the judge image bakes one: every row synthetic."""
    conn = db("judge.db")
    migrate.migrate(conn)
    repo = Repository(conn)
    repo.insert_entry(
        created_at_ms=now_ms(),
        captured_tz="UTC",
        tz_offset_min=0,
        modality="text",
        default_policy="cloud-assisted",
        status="queued",
        capture_profile="cloud",
        raw_text="[synthetic] an idea",
        is_synthetic=True,
    )
    return conn, tmp_path / "judge.db"


class TestTheCheckPasses:
    def test_a_fully_synthetic_database_is_shippable(self, seeded):
        _, path = seeded

        result = _run(path)

        assert result.returncode == 0, result.stderr
        assert "clean" in result.stdout


class TestTheCheckCanFail:
    """A check that has never refused anything is a hypothesis."""

    def test_a_real_entry_is_refused(self, db, tmp_path):
        conn = db("real.db")
        migrate.migrate(conn)
        Repository(conn).insert_entry(
            created_at_ms=now_ms(),
            captured_tz="UTC",
            tz_offset_min=0,
            modality="text",
            default_policy="local-only",
            status="queued",
            capture_profile="spark",
            raw_text="something the subject actually wrote",
            is_synthetic=False,
        )

        result = _run(tmp_path / "real.db")

        assert result.returncode == 1
        assert "entries holds 1 unmarked" in result.stderr

    def test_a_payload_is_refused_even_when_marked_synthetic(
        self, seeded
    ):
        """The forbidden table is forbidden whatever the row says about itself.

        A payload is raw local-only content by construction; a flag claiming
        otherwise is a claim, and this is the last place to believe one.
        """
        conn, path = seeded
        repo = Repository(conn)
        agent = repo.insert_agent(
            name="synthetic-researcher",
            role="researcher",
            version=1,
            prompt_path="p.md",
            prompt_sha="0" * 64,
        )
        invocation = repo.insert_agent_invocation(
            agent_id=agent,
            started_at_ms=now_ms(),
            is_synthetic=True,
        )
        call_id = repo.insert_model_call(
            agent_invocation_id=invocation,
            provider="local-vllm",
            compute_profile="cloud",
            model="m",
            policy="cloud-assisted",
            estimated_cost_usd=0.0,
            is_synthetic=True,
        )
        conn.execute(
            "INSERT INTO model_call_payloads (model_call_id, prompt_path, "
            "completion_path, captured_at_ms) VALUES (?, ?, ?, ?)",
            (
                call_id,
                "data/payloads/2026-09/x.prompt.json",
                "data/payloads/2026-09/x.completion.json",
                now_ms(),
            ),
        )
        conn.commit()

        result = _run(path)

        assert result.returncode == 1
        assert "model_call_payloads" in result.stderr
        assert "raw local-only content" in result.stderr

    def test_a_missing_database_is_not_reported_as_clean(self, tmp_path):
        """Silence on an absent file is how a build ships nothing and passes."""
        result = _run(tmp_path / "absent.db")

        assert result.returncode == 2
        assert "no database" in result.stderr
