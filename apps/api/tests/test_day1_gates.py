"""The day-1 pass gates from docs/WEEK_ONE.md.

Kept as their own file so the gates are auditable as a unit: if this file is
green, day 1 is done. Each test names the gate it covers.
"""

from __future__ import annotations

import sqlite3

import pytest

from secondshift.airlock.capability import build_report
from secondshift.airlock.policy import Policy
from secondshift.airlock.quarantine import Quarantine
from secondshift.config import (
    CUDA,
    LOCAL_REASONER,
    SPEECH_STACK,
    Capability,
    ProbeResult,
    Profile,
    resolve_profile,
)
from secondshift.db import migrate
from secondshift.db.connection import now_ms
from secondshift.providers.base import Message


def _no_local_stack() -> ProbeResult:
    return ProbeResult(
        {
            CUDA: Capability(CUDA, False, "no CUDA device detected"),
            LOCAL_REASONER: Capability(
                LOCAL_REASONER, False, "local reasoner endpoint 127.0.0.1:8000 unreachable"
            ),
            SPEECH_STACK: Capability(SPEECH_STACK, False, "speech stack not importable"),
        }
    )


def _degraded() -> ProbeResult:
    return ProbeResult(
        {
            CUDA: Capability(CUDA, True, "nvidia-smi present"),
            LOCAL_REASONER: Capability(
                LOCAL_REASONER, False, "local reasoner endpoint 127.0.0.1:8000 unreachable"
            ),
            SPEECH_STACK: Capability(SPEECH_STACK, True, "importable"),
        }
    )


def test_gate_6_1_migrations_apply_clean(db):
    """Gate 6.1 — migrations apply clean against a fresh database."""
    conn = db("gate.db")
    expected = [m.version for m in migrate.discover()]
    assert migrate.migrate(conn) == expected
    assert migrate.current_version(conn) == max(expected)
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_gate_6_2_nested_tree_with_model_calls(recorder, repo, run_id, agent_id):
    """Gate 6.2 — a run with invocations at depth >= 2 and attached model calls."""
    with recorder.invocation(agent_id, run_id=run_id, stage="brief") as root:
        recorder.record_model_call(
            provider="local-vllm", model="m", policy="local-only", prompt_tokens=10
        )
        with recorder.invocation(agent_id, stage="research") as middle:
            recorder.record_model_call(
                provider="token-factory",
                model="nemotron-3-super",
                policy="cloud-assisted",
                prompt_tokens=100,
                completion_tokens=50,
            )
            with recorder.invocation(agent_id, stage="critique") as leaf:
                recorder.record_model_call(
                    provider="local-vllm",
                    model="m",
                    policy="local-only",
                    prompt_tokens=5,
                )

    tree = repo.invocation_tree(run_id)
    by_id = {r["id"]: r for r in tree}
    assert max(r["depth"] for r in tree) >= 2

    # The tree reads back in the shape it was written.
    assert by_id[root]["parent_invocation_id"] is None
    assert by_id[middle]["parent_invocation_id"] == root
    assert by_id[leaf]["parent_invocation_id"] == middle
    assert all(r["outcome"] == "success" for r in tree)

    calls = repo.model_calls_for_run(run_id)
    assert len(calls) == 3
    assert {c["agent_invocation_id"] for c in calls} == {root, middle, leaf}


def test_gate_6_3_airlock_constraint_rejects_remote_local_only(repo, run_id):
    """Gate 6.3 — the database refuses the write, not merely the caller.

    Deliberately bypasses the call-time guard in `airlock.policy` so this
    exercises the CHECK constraint itself. Both layers must hold independently.
    """
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        repo.insert_model_call(
            provider="token-factory",
            compute_profile="spark",
            model="nemotron-3-ultra",
            policy="local-only",
            estimated_cost_usd=0.0,
            run_id=run_id,
        )
    assert repo.model_calls_for_run(run_id) == []


def test_gate_6_3b_permitted_combinations_still_write(repo, run_id):
    """The constraint blocks the breach without blocking legitimate work."""
    local = repo.insert_model_call(
        provider="local-vllm",
        compute_profile="spark",
        model="m",
        policy="local-only",
        estimated_cost_usd=0.0,
        run_id=run_id,
    )
    cloud = repo.insert_model_call(
        provider="token-factory",
        compute_profile="spark",
        model="nemotron-3-super",
        policy="cloud-assisted",
        estimated_cost_usd=0.004,
        run_id=run_id,
    )
    assert {c["id"] for c in repo.model_calls_for_run(run_id)} == {local, cloud}


def test_gate_6_4_no_cuda_resolves_to_cloud():
    """Gate 6.4 — profile resolution returns cloud on a machine with no CUDA."""
    resolved = resolve_profile(env={}, probe_result=_no_local_stack())
    assert resolved.profile is Profile.CLOUD


def test_gate_6_5_degraded_profile_quarantines_local_only(repo):
    """Gate 6.5 — quarantined rather than dispatched, and the cause is named."""
    private = repo.insert_entry(
        created_at_ms=now_ms(),
        captured_tz="America/Los_Angeles",
        tz_offset_min=-420,
        modality="text",
        default_policy="local-only",
        status="queued",
        capture_profile="spark",
        raw_text="something private",
    )
    shared = repo.insert_entry(
        created_at_ms=now_ms(),
        captured_tz="America/Los_Angeles",
        tz_offset_min=-420,
        modality="text",
        default_policy="cloud-assisted",
        status="queued",
        capture_profile="spark",
        raw_text="something shareable",
    )

    report = build_report(resolve_profile(env={}, probe_result=_degraded()))
    quarantine = Quarantine(repo, report)

    blocked = quarantine.blocked()
    assert [s.entry_id for s in blocked] == [private]
    assert "endpoint" in (blocked[0].cause or "")
    assert blocked[0].resolution.effective_policy is Policy.LOCAL_ONLY

    # Cloud-assisted work continues; a degraded profile reduces what runs.
    assert [s.entry_id for s in quarantine.dispatchable()] == [shared]

    # The report names the finding rather than a generic message.
    assert "endpoint" in (report.reason_for(Policy.LOCAL_ONLY) or "")


def test_gate_end_to_end_local_only_costs_nothing(recorder, repo, run_id, agent_id):
    """The Airlock demo, proven by instrumentation rather than asserted.

    A local-only idea produces a real artifact at exactly zero cloud spend.
    """
    from secondshift.providers.registry import Registry

    providers = Registry(recorder).bind("spark")
    with recorder.invocation(agent_id, run_id=run_id, stage="brief"):
        providers.reasoner.complete(
            [Message("user", "build me something")], policy="local-only"
        )

    row = repo.connection.execute(
        "SELECT COALESCE(SUM(estimated_cost_usd), 0) AS spend, "
        "COALESCE(SUM(CASE WHEN provider IN ('token-factory','nebius-job') "
        "THEN total_tokens END), 0) AS cloud_tokens "
        "FROM model_calls WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    assert row["spend"] == 0.0
    assert row["cloud_tokens"] == 0
