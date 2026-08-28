"""The synthetic night generator: density, determinism, and exclusion.

The tests live here rather than beside the generator because everything they
assert is a claim about the schema — that a generated night satisfies the
queries a real night view issues, and that the rollups and the dispatch set
cannot see it. Those fixtures are here.
"""

from __future__ import annotations

import pathlib

import sqlite3
import sys
from collections import Counter
from pathlib import Path

import pytest

from secondshift.db import connection, migrate
from secondshift.db.ids import timestamp_ms
from secondshift.db.repository import Repository
from secondshift.telemetry.failures import FailureType

# `packages/seed` is a sibling distribution, installed alongside `secondshift`
# on a deployment but not by this application's own editable install.
_SEED_PACKAGE = Path(__file__).resolve().parents[3] / "packages" / "seed"
if str(_SEED_PACKAGE) not in sys.path:
    sys.path.insert(0, str(_SEED_PACKAGE))

from secondshift_seed import generate_night  # noqa: E402
from secondshift_seed.__main__ import main  # noqa: E402
from secondshift_seed.night import STAGES  # noqa: E402

MS_PER_HOUR = 3_600_000

#: Everything a night is made of, in the order it is written. The determinism
#: comparison walks exactly these; `agents` is deliberately absent and gets its
#: own test explaining why.
NIGHT_TABLES = (
    "entries",
    "runs",
    "run_stages",
    "agent_invocations",
    "model_calls",
    "tool_calls",
    "events",
    "failures",
    "artifacts",
)

#: The flagged tables a generated night must actually put rows in. Without this
#: the audit below would pass just as happily against a generator that wrote
#: nothing at all. `run_stages` is absent because the schema gives it no
#: `is_synthetic` column: a stage is reachable only through its run, and the run
#: carries the flag.
POPULATED_TABLES = frozenset(set(NIGHT_TABLES) - {"run_stages"})

_EVENT_KINDS = frozenset(
    {
        "search",
        "extract",
        "job_dispatch",
        "job_complete",
        "file_write",
        "model_call",
        "stage_start",
        "stage_end",
        "decision",
        "error",
        "note",
    }
)
_SEVERITIES = frozenset({"debug", "info", "warn", "error"})


@pytest.fixture
def open_night_db(tmp_path):
    """Migrated databases, all closed at teardown.

    A factory rather than one connection: determinism is a claim about separate
    databases and cannot be checked inside a single one. An unclosed sqlite3
    connection raises during interpreter finalization, which
    `filterwarnings = ["error"]` correctly turns into a failure.
    """
    opened: list[sqlite3.Connection] = []

    def _open(name: str = "night.db") -> Repository:
        conn = connection.connect(tmp_path / name)
        migrate.migrate(conn)
        opened.append(conn)
        return Repository(conn)

    yield _open
    for conn in opened:
        conn.close()


def _dump(repo: Repository, table: str) -> list[tuple]:
    rows = repo.connection.execute(f"SELECT * FROM {table} ORDER BY 1")
    return [tuple(row) for row in rows]


def _flagged_tables(repo: Repository) -> list[str]:
    """Every table carrying `is_synthetic`, read from the schema itself.

    Discovered rather than listed, so a table added by a later migration is
    audited the day it appears instead of the day someone remembers it.
    """
    names = [
        row["name"]
        for row in repo.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    ]
    return [
        name
        for name in names
        if any(
            column["name"] == "is_synthetic"
            for column in repo.connection.execute(f"PRAGMA table_info({name})")
        )
    ]


def _real_run(repo: Repository, *, night_of: str, cost_usd: float = 0.25) -> str:
    """A small real run, so exclusion can be told apart from an empty database."""
    entry_id = repo.insert_entry(
        created_at_ms=1_787_800_000_000,
        captured_tz="America/Los_Angeles",
        tz_offset_min=-420,
        modality="text",
        default_policy="cloud-assisted",
        status="queued",
        capture_profile="spark",
        raw_text="a real idea, captured by a person",
    )
    run_id = repo.insert_run(
        entry_id=entry_id,
        night_of=night_of,
        effective_policy="cloud-assisted",
        policy_source="entry-default",
        compute_profile="spark",
        started_at_ms=1_787_810_000_000,
    )
    repo.insert_model_call(
        provider="token-factory",
        compute_profile="spark",
        model="hosted-reasoner",
        policy="cloud-assisted",
        estimated_cost_usd=cost_usd,
        prompt_tokens=1_000,
        completion_tokens=500,
        total_tokens=1_500,
        run_id=run_id,
        ts_ms=1_787_810_500_000,
    )
    return run_id


class TestDensity:
    def test_a_night_has_a_run_stages_a_deep_tree_and_hundreds_of_events(
        self, open_night_db
    ):
        repo = open_night_db()
        night = generate_night(repo, seed=7)

        run = repo.connection.execute(
            "SELECT * FROM runs WHERE id = ?", (night.run_id,)
        ).fetchone()
        assert run["entry_id"] == night.subject_entry_id
        assert run["effective_policy"] == "cloud-assisted"
        assert run["is_synthetic"] == 1

        stages = repo.connection.execute(
            "SELECT stage, seq FROM run_stages WHERE run_id = ? ORDER BY seq",
            (night.run_id,),
        ).fetchall()
        assert [s["stage"] for s in stages] == list(STAGES)
        assert [s["seq"] for s in stages] == list(range(1, len(STAGES) + 1))

        tree = repo.invocation_tree(night.run_id)
        depths = {row["depth"] for row in tree}
        assert max(depths) >= 3
        # Every level between the root and the deepest leaf is occupied; a tree
        # that skipped one would report a depth it does not have.
        assert depths == set(range(max(depths) + 1))

        seen: set[str] = set()
        for row in tree:
            parent = row["parent_invocation_id"]
            assert parent is None or parent in seen, "a child preceded its parent"
            seen.add(row["id"])

        timeline = repo.timeline(night.run_id)
        assert len(timeline) >= 400
        assert night.event_count >= len(timeline)
        assert len({row["lane"] for row in timeline}) > 1

    def test_events_are_spread_across_the_night_rather_than_clustered(
        self, open_night_db
    ):
        repo = open_night_db()
        night = generate_night(repo, seed=7)
        stamps = [row["ts_ms"] for row in repo.timeline(night.run_id)]

        span = max(stamps) - min(stamps)
        assert span >= 5 * MS_PER_HOUR

        # Every eighth of the night carries work. A run that only looks spread
        # out because one late event stretched the axis would leave gaps here.
        buckets = Counter(min(7, (ts - min(stamps)) * 8 // span) for ts in stamps)
        assert sorted(buckets) == list(range(8))
        assert min(buckets.values()) >= 10

    def test_the_tree_uses_more_than_one_agent_role(self, open_night_db):
        repo = open_night_db()
        night = generate_night(repo, seed=7)
        roles = {
            row["role"]
            for row in repo.connection.execute(
                "SELECT DISTINCT a.role FROM agent_invocations i "
                "JOIN agents a ON a.id = i.agent_id WHERE i.run_id = ?",
                (night.run_id,),
            )
        }
        assert roles == {
            "interviewer",
            "researcher",
            "architect",
            "builder",
            "critic",
            "distiller",
        }


class TestDeterminism:
    def test_one_seed_writes_the_same_night_into_two_databases(self, open_night_db):
        left, right = open_night_db("left.db"), open_night_db("right.db")

        first = generate_night(left, seed=11)
        second = generate_night(right, seed=11)

        assert first == second
        for table in NIGHT_TABLES:
            assert _dump(left, table) == _dump(right, table), table

    def test_the_agent_roster_differs_only_in_its_wall_clock_stamp(self, open_night_db):
        """The one value a seed cannot reproduce, named rather than left to be
        found later as flakiness.

        `Repository.insert_agent` stamps `created_at_ms` from the clock and
        offers no override, so two runs of one seed disagree on it. The roster
        is a catalog rather than night data and nothing renders that column, but
        a determinism claim that quietly excluded a column would be worthless.
        """
        left, right = open_night_db("left.db"), open_night_db("right.db")
        generate_night(left, seed=11)
        generate_night(right, seed=11)

        columns = "id, name, role, version, prompt_path, prompt_sha"
        query = f"SELECT {columns} FROM agents ORDER BY name"
        assert [tuple(r) for r in left.connection.execute(query)] == [
            tuple(r) for r in right.connection.execute(query)
        ]
        stamps = [
            r["created_at_ms"]
            for repo in (left, right)
            for r in repo.connection.execute("SELECT created_at_ms FROM agents")
        ]
        assert all(stamp > 0 for stamp in stamps)

    def test_two_seeds_write_different_nights(self, open_night_db):
        left, right = open_night_db("left.db"), open_night_db("right.db")

        first = generate_night(left, seed=11)
        second = generate_night(right, seed=12)

        assert first.run_id != second.run_id
        assert _dump(left, "model_calls") != _dump(right, "model_calls")
        assert _dump(left, "events") != _dump(right, "events")

    def test_generated_identifiers_are_ulids_carrying_their_own_instant(
        self, open_night_db
    ):
        """Ordering is `created_at_ms, id`. If the identifier's embedded instant
        disagreed with the recorded one, that would sort by two clocks."""
        repo = open_night_db()
        night = generate_night(repo, seed=7)

        for row in repo.connection.execute("SELECT id, created_at_ms FROM entries"):
            assert timestamp_ms(row["id"]) == row["created_at_ms"]
        for row in repo.connection.execute("SELECT id, ts_ms FROM model_calls"):
            assert timestamp_ms(row["id"]) == row["ts_ms"]
        assert timestamp_ms(night.run_id) == night.started_at_ms


class TestSyntheticFlag:
    def test_every_row_that_can_be_marked_synthetic_is(self, open_night_db):
        repo = open_night_db()
        generate_night(repo, seed=7)

        written: set[str] = set()
        for table in _flagged_tables(repo):
            total, real = repo.connection.execute(
                f"SELECT COUNT(*), COALESCE(SUM(is_synthetic = 0), 0) FROM {table}"
            ).fetchone()
            assert real == 0, f"{table} holds {real} unflagged generated rows"
            if total:
                written.add(table)

        assert written == POPULATED_TABLES

    def test_the_cost_and_totals_views_ignore_a_generated_night(self, open_night_db):
        repo = open_night_db()
        real_run = _real_run(repo, night_of="2026-08-27", cost_usd=0.25)
        night = generate_night(repo, seed=7, night_of="2026-08-27")

        # The generated night has real spend to hide: an exclusion test against
        # a night that cost nothing proves nothing.
        generated_spend = repo.connection.execute(
            "SELECT SUM(estimated_cost_usd) AS spend FROM model_calls WHERE run_id = ?",
            (night.run_id,),
        ).fetchone()["spend"]
        assert generated_spend > 0.0

        costs = repo.connection.execute("SELECT * FROM run_cost").fetchall()
        assert [row["run_id"] for row in costs] == [real_run]

        totals = repo.connection.execute("SELECT * FROM night_totals").fetchone()
        assert totals["runs"] == 1
        assert totals["model_cost_usd"] == 0.25
        assert totals["cloud_tokens"] == 1_500
        assert totals["tool_credits"] == 0

    def test_generated_queued_entries_are_never_dispatched(self, open_night_db):
        repo = open_night_db()
        _real_run(repo, night_of="2026-08-27")
        night = generate_night(repo, seed=7, night_of="2026-08-27")

        queued = {
            row["id"]
            for row in repo.connection.execute(
                "SELECT id FROM entries WHERE status = 'queued' AND is_synthetic = 1"
            )
        }
        assert queued, "the night generated no queued entries to exclude"

        eligible = {row["id"] for row in repo.dispatch_eligible_entries()}
        assert not eligible & set(night.entry_ids)
        # The real entry is still dispatchable, so this is exclusion rather than
        # an empty eligibility set.
        assert len(eligible) == 1

        reasons = {
            row["id"]: reason
            for row, reason in repo.ineligible_entries()
            if row["id"] in queued
        }
        assert reasons == {
            entry_id: "synthetic entries are never dispatched" for entry_id in queued
        }

    def test_a_generated_timeline_renders_from_scalar_columns(self, open_night_db):
        repo = open_night_db()
        night = generate_night(repo, seed=7)
        timeline = repo.timeline(night.run_id)

        assert [row["ts_ms"] for row in timeline] == sorted(
            row["ts_ms"] for row in timeline
        )
        assert {row["kind"] for row in timeline} <= _EVENT_KINDS
        assert {row["severity"] for row in timeline} <= _SEVERITIES
        assert all(row["label"].strip() for row in timeline)

        # `duration_ms` renders as a bar when set and a tick when null. A feed
        # of only one of the two never exercises the other path.
        durations = [row["duration_ms"] for row in timeline]
        assert any(d is not None and d > 0 for d in durations)
        assert any(d is None for d in durations)

        attached = [row for row in timeline if row["agent_invocation_id"] is not None]
        assert len(attached) > len(timeline) // 2

    def test_capture_events_stay_readable_without_a_run(self, open_night_db):
        """Migration 0002 added `entry_id` so capture is not exempt from
        telemetry. A generated night has to exercise that path too."""
        repo = open_night_db()
        night = generate_night(repo, seed=7)

        history = repo.entry_history(night.subject_entry_id)
        assert [row["kind"] for row in history][0] == "note"
        assert history[0]["run_id"] is None


class TestConstraints:
    def test_a_local_only_night_names_only_local_providers(self, open_night_db):
        repo = open_night_db()
        night = generate_night(repo, seed=7, policy="local-only")

        pairs = {
            (row["policy"], row["provider"])
            for row in repo.model_calls_for_run(night.run_id)
        }
        assert pairs == {("local-only", "local-vllm")}

        # Nothing leaves the machine, so there is no external tool call either.
        assert night.tool_call_ids == ()
        # The airlock does not cost the night its density.
        assert len(repo.timeline(night.run_id)) >= 400

    def test_the_database_still_refuses_the_breach_the_generator_avoids(
        self, open_night_db
    ):
        """The CHECK is what makes the airlock a guarantee rather than a habit.
        If it stopped firing, the local-only test above would pass for the wrong
        reason."""
        repo = open_night_db()
        night = generate_night(repo, seed=7, policy="local-only")

        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            repo.insert_model_call(
                provider="token-factory",
                compute_profile="spark",
                model="hosted-reasoner",
                policy="local-only",
                estimated_cost_usd=0.0,
                run_id=night.run_id,
                is_synthetic=True,
            )

    def test_generated_telemetry_populates_the_columns_the_night_view_reads(
        self, open_night_db
    ):
        repo = open_night_db()
        night = generate_night(repo, seed=7)

        for call in repo.model_calls_for_run(night.run_id):
            assert call["total_tokens"] == (
                call["prompt_tokens"]
                + call["completion_tokens"]
                + call["reasoning_tokens"]
            )
            assert call["latency_ms"] > 0
            assert 0 < call["time_to_first_token_ms"] <= call["latency_ms"]
            assert call["compute_profile"] == "spark"
            assert call["estimated_cost_usd"] >= 0.0

        # Cost follows the provider rather than being sprinkled on: local
        # inference is metered at zero, and every cloud call carries spend.
        by_provider = {
            row["provider"]: (row["spend"], row["redacted"])
            for row in repo.connection.execute(
                "SELECT provider, SUM(estimated_cost_usd) AS spend, "
                "MIN(redaction_applied) AS redacted FROM model_calls "
                "WHERE run_id = ? GROUP BY provider",
                (night.run_id,),
            )
        }
        assert by_provider["local-vllm"] == (0.0, 0)
        for provider in ("token-factory", "nebius-job"):
            spend, redacted = by_provider[provider]
            assert spend > 0.0
            assert redacted == 1, f"{provider} egress was not marked redacted"

        for call in repo.connection.execute(
            "SELECT * FROM tool_calls WHERE run_id = ?", (night.run_id,)
        ):
            assert call["query_redacted"].startswith("[synthetic]")
            assert call["credits"] > 0.0
            assert call["outcome"] in {"success", "error", "quota"}

    def test_a_second_night_shares_the_agent_roster(self, open_night_db):
        """`agents` carries `UNIQUE(name, version)` and no synthetic flag, so a
        roster is a catalog rather than night data. A judge deployment holds
        several seeded nights, and the second must reuse it rather than collide
        with it."""
        repo = open_night_db()
        first = generate_night(repo, seed=11)
        second = generate_night(repo, seed=12, night_of="2026-08-28")

        roster = {
            row["id"] for row in repo.connection.execute("SELECT id FROM agents")
        }
        assert len(roster) == 6

        used = {
            row["agent_id"]
            for run_id in (first.run_id, second.run_id)
            for row in repo.invocation_tree(run_id)
        }
        assert used == roster

    def test_every_invocation_is_closed_with_an_outcome(self, open_night_db):
        repo = open_night_db()
        night = generate_night(repo, seed=7)

        tree = repo.invocation_tree(night.run_id)
        assert len(tree) == len(night.invocation_ids)
        for row in tree:
            assert row["ended_at_ms"] >= row["started_at_ms"]
            assert row["outcome"] in {"success", "degraded", "failed"}
        assert {row["outcome"] for row in tree} == {"success", "degraded", "failed"}


class TestFailure:
    def test_generated_failures_are_typed_and_attached_to_invocations(
        self, open_night_db
    ):
        repo = open_night_db()
        night = generate_night(repo, seed=7)

        rows = repo.connection.execute(
            "SELECT * FROM failures WHERE run_id = ?", (night.run_id,)
        ).fetchall()
        assert len(rows) == len(night.failure_ids) >= 6

        taxonomy = {str(t) for t in FailureType}
        assert {row["type"] for row in rows} <= taxonomy
        assert len({row["type"] for row in rows}) >= 5

        invocations = set(night.invocation_ids)
        for row in rows:
            assert row["agent_invocation_id"] in invocations
            assert row["signature"].startswith(row["type"] + ":")
            assert row["message"]
            assert row["is_synthetic"] == 1

        failed = {
            r["id"]
            for r in repo.invocation_tree(night.run_id)
            if r["outcome"] == "failed"
        }
        assert failed == {row["agent_invocation_id"] for row in rows}

    def test_generated_failures_stay_out_of_the_ledger(self, open_night_db):
        repo = open_night_db()
        real_run = _real_run(repo, night_of="2026-08-27")
        repo.insert_failure(
            failure_type="model_timeout",
            signature="model_timeout:research:realsignature",
            message="the real reasoner timed out",
            run_id=real_run,
        )
        generate_night(repo, seed=7, night_of="2026-08-27")

        ledger = repo.failure_ledger()
        assert [row["signature"] for row in ledger] == [
            "model_timeout:research:realsignature"
        ]
        assert ledger[0]["recurrence_count"] == 1


class TestCommandLine:
    def test_it_seeds_the_database_it_is_given(self, tmp_path, capsys):
        target = tmp_path / "seeded.db"
        assert main(["--seed", "5", "--db", str(target), "--policy", "local-only"]) == 0

        conn = connection.connect(target)
        try:
            repo = Repository(conn)
            run = conn.execute("SELECT * FROM runs").fetchone()
            assert run["effective_policy"] == "local-only"
            assert run["is_synthetic"] == 1
            assert len(repo.timeline(run["id"])) >= 400
        finally:
            conn.close()

        assert f"seeded run {run['id']}" in capsys.readouterr().out

    def test_it_refuses_a_date_it_cannot_parse(self, tmp_path):
        with pytest.raises(SystemExit) as exit_info:
            main(["--seed", "5", "--db", str(tmp_path / "x.db"), "--night-of", "soon"])
        assert exit_info.value.code == 2
        assert not (tmp_path / "x.db").exists()


@pytest.fixture
def fresh_repo(tmp_path):
    """Independent databases, closed at teardown.

    A plain factory leaked connections, and `filterwarnings = ["error"]` turns a
    ResourceWarning at garbage-collection time into an error attributed to
    whichever test ran next — a failure that moves depending on ordering, which
    is the worst kind to debug.
    """
    from secondshift.db import connection, migrate

    opened = []

    def _make() -> Repository:
        conn = connection.connect(tmp_path / f"seed-{len(opened)}.db")
        migrate.migrate(conn)
        opened.append(conn)
        return Repository(conn)

    yield _make
    for conn in opened:
        conn.close()


class TestVariants:
    """The build fan-out. Unreadable as a comparison without a group and a rank."""

    def test_a_group_holds_several_ranked_variants(self, repo):
        night = generate_night(repo, seed=31)
        rows = repo.connection.execute(
            "SELECT variant_index, variant_rank FROM artifacts "
            "WHERE variant_group = ? ORDER BY variant_index",
            (night.variant_group,),
        ).fetchall()
        assert len(rows) >= 3
        assert len({r["variant_rank"] for r in rows}) == len(rows)
        assert sorted(r["variant_rank"] for r in rows) == list(range(1, len(rows) + 1))

    def test_rank_is_not_merely_the_generation_order(self, fresh_repo):
        """A renderer assuming rank equals index must be wrong on this data."""
        differs = False
        for seed in range(20):
            fresh = fresh_repo()
            night = generate_night(fresh, seed=seed)
            rows = fresh.connection.execute(
                "SELECT variant_index, variant_rank FROM artifacts "
                "WHERE variant_group = ? ORDER BY variant_index",
                (night.variant_group,),
            ).fetchall()
            if any(r["variant_index"] + 1 != r["variant_rank"] for r in rows):
                differs = True
                break
        assert differs

    def test_non_variant_artifacts_carry_no_group(self, repo):
        night = generate_night(repo, seed=31)
        rows = repo.connection.execute(
            "SELECT kind, variant_group FROM artifacts WHERE run_id = ?", (night.run_id,)
        ).fetchall()
        singles = [r for r in rows if r["kind"] != "build"]
        assert singles and all(r["variant_group"] is None for r in singles)

    def test_artifacts_are_synthetic_and_attributed(self, repo):
        night = generate_night(repo, seed=31)
        rows = repo.connection.execute(
            "SELECT is_synthetic, produced_by_invocation_id, run_id, entry_id "
            "FROM artifacts WHERE run_id = ?",
            (night.run_id,),
        ).fetchall()
        assert rows and all(r["is_synthetic"] == 1 for r in rows)
        assert all(r["produced_by_invocation_id"] in night.invocation_ids for r in rows)
        assert all(r["entry_id"] == night.subject_entry_id for r in rows)

    def test_artifacts_are_deterministic(self, fresh_repo):
        a, b = fresh_repo(), fresh_repo()
        first, second = generate_night(a, seed=99), generate_night(b, seed=99)
        assert first.artifact_ids == second.artifact_ids
        assert first.variant_group == second.variant_group

    def test_a_generated_night_is_absent_from_accepted_artifact_cost(self, repo):
        """cost_per_accepted_artifact must not count seeded work."""
        night = generate_night(repo, seed=31)
        repo.connection.execute(
            "INSERT INTO outcomes (id, entry_id, artifact_id, ts_ms, label, is_synthetic) "
            "VALUES ('o1', ?, ?, 1, 'keep', 1)",
            (night.subject_entry_id, night.artifact_ids[0]),
        )
        rows = repo.connection.execute("SELECT * FROM cost_per_accepted_artifact").fetchall()
        assert rows == []
