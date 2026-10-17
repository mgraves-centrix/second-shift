"""Telemetry from out-of-process work: collected by the poller, counted once.

The design took the option with no inbound path. A job writes what it did beside
what it produced, and `Executor.await_result` — which already polls — collects
that report and hands it to `Recorder.ingest_external` locally, under the one
writer's lock. Nothing on the machine that holds the brain listens for a job.

What that leaves to get right is everything after the bytes arrive: reading the
report strictly, attaching it under the right dispatcher, recording it once
however many times it is collected, and never presenting a job whose report
never came as a job that cost nothing.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from secondshift.providers.base import (
    RECORDED_IN_PROCESS,
    Executor,
    JobHandle,
    JobResult,
    JobSpec,
)
from secondshift.providers.null import InProcessExecutor
from secondshift.telemetry.recorder import ExternalInvocation, ExternalModelCall
from secondshift.telemetry.reports import UnreadableReport, parse_report


def _report(dispatcher, agent_id, **overrides):
    report = {
        "dispatching_invocation_id": dispatcher,
        "invocations": [
            {
                "local_id": "01JOBINV0000000000000000AA",
                "agent_id": agent_id,
                "parent_local_id": None,
                "stage": "build",
                "input_summary": "variant 1",
                "started_at_ms": 1_000,
                "ended_at_ms": 2_000,
                "outcome": "success",
            }
        ],
        "model_calls": [
            {
                "local_id": "01JOBCALL000000000000000AA",
                "parent_local_id": "01JOBINV0000000000000000AA",
                "provider": "token-factory",
                "model": "nemotron-3-super",
                "policy": "cloud-assisted",
                "compute_profile": "cloud",
                "prompt_tokens": 1_000,
                "completion_tokens": 500,
                "total_tokens": 1_500,
                "latency_ms": 900,
                "ts_ms": 1_500,
            }
        ],
    }
    report.update(overrides)
    return json.dumps(report)


@pytest.fixture
def dispatcher(recorder, run_id, agent_id):
    with recorder.invocation(agent_id, run_id=run_id) as invocation_id:
        pass
    return invocation_id


class TestTheSameWorkIsRecordedOnce:
    def _ingest(self, recorder, dispatcher, agent_id):
        invocations, calls = parse_report(
            _report(dispatcher, agent_id), dispatcher=dispatcher
        )
        return recorder.ingest_external(
            dispatcher, invocations=invocations, model_calls=calls
        )

    def test_a_second_collection_adds_no_rows(
        self, recorder, repo, run_id, agent_id, dispatcher
    ):
        first = self._ingest(recorder, dispatcher, agent_id)
        before = (len(repo.invocation_tree(run_id)), len(repo.model_calls_for_run(run_id)))

        second = self._ingest(recorder, dispatcher, agent_id)

        assert second == first
        assert (len(repo.invocation_tree(run_id)), len(repo.model_calls_for_run(run_id))) == before

    def test_the_reporter_need_not_say_it_is_repeating_itself(
        self, recorder, repo, run_id, agent_id, dispatcher
    ):
        """Enforced by the recorder from the ids the job gave its work when it
        did it, not by a flag the reporter could forget to set."""
        self._ingest(recorder, dispatcher, agent_id)
        self._ingest(recorder, dispatcher, agent_id)
        self._ingest(recorder, dispatcher, agent_id)

        costs = [r["estimated_cost_usd"] for r in repo.model_calls_for_run(run_id)]
        assert len(costs) == 1

    def test_the_same_ids_under_another_dispatcher_are_other_work(
        self, recorder, repo, run_id, agent_id, dispatcher
    ):
        """Keyed by dispatcher and id together. Two variants whose jobs happened
        to number their work the same way are two variants."""
        with recorder.invocation(agent_id, run_id=run_id) as other:
            pass
        self._ingest(recorder, dispatcher, agent_id)
        invocations, calls = parse_report(_report(other, agent_id), dispatcher=other)
        recorder.ingest_external(other, invocations=invocations, model_calls=calls)

        assert len(repo.model_calls_for_run(run_id)) == 2


class TestAReportIsReadStrictly:
    def test_a_report_round_trips(self, agent_id, dispatcher):
        invocations, calls = parse_report(_report(dispatcher, agent_id), dispatcher=dispatcher)

        assert invocations == [
            ExternalInvocation(
                local_id="01JOBINV0000000000000000AA",
                agent_id=agent_id,
                parent_local_id=None,
                stage="build",
                input_summary="variant 1",
                started_at_ms=1_000,
                ended_at_ms=2_000,
                outcome="success",
            )
        ]
        assert calls[0] == ExternalModelCall(
            local_id="01JOBCALL000000000000000AA",
            parent_local_id="01JOBINV0000000000000000AA",
            provider="token-factory",
            model="nemotron-3-super",
            policy="cloud-assisted",
            compute_profile="cloud",
            prompt_tokens=1_000,
            completion_tokens=500,
            total_tokens=1_500,
            latency_ms=900,
            ts_ms=1_500,
        )

    def test_a_report_for_another_dispatcher_is_refused(self, agent_id, dispatcher):
        """The pull model's authentication: a report is believed only for the
        dispatch that produced it, and nothing in it chooses where it attaches."""
        with pytest.raises(UnreadableReport, match="dispatch"):
            parse_report(_report("01SOMEONEELSE0000000000000", agent_id), dispatcher=dispatcher)

    @pytest.mark.parametrize("field", ["local_id", "policy", "prompt_tokens", "provider"])
    def test_a_model_call_missing_a_field_is_refused_not_dropped(
        self, agent_id, dispatcher, field
    ):
        """A skipped model call is a cloud night that reads as cheaper than it
        was. Refusing the whole report leaves the run visibly unaccounted."""
        report = json.loads(_report(dispatcher, agent_id))
        del report["model_calls"][0][field]

        with pytest.raises(UnreadableReport, match=field):
            parse_report(json.dumps(report), dispatcher=dispatcher)

    def test_a_field_nobody_maps_is_refused(self, agent_id, dispatcher):
        report = json.loads(_report(dispatcher, agent_id))
        report["model_calls"][0]["cost_usd"] = 0.0

        with pytest.raises(UnreadableReport, match="cost_usd"):
            parse_report(json.dumps(report), dispatcher=dispatcher)

    def test_text_that_is_not_a_report_is_refused(self, dispatcher):
        with pytest.raises(UnreadableReport):
            parse_report("Traceback (most recent call last):", dispatcher=dispatcher)

    def test_a_boolean_is_not_a_token_count(self, agent_id, dispatcher):
        report = json.loads(_report(dispatcher, agent_id))
        report["model_calls"][0]["prompt_tokens"] = True

        with pytest.raises(UnreadableReport, match="prompt_tokens"):
            parse_report(json.dumps(report), dispatcher=dispatcher)


class TestParentsComeFirst:
    def test_a_child_listed_before_its_parent_is_reordered(self, agent_id, dispatcher):
        report = json.loads(_report(dispatcher, agent_id))
        child = dict(report["invocations"][0], local_id="CHILD", parent_local_id=report["invocations"][0]["local_id"])
        report["invocations"].insert(0, child)

        invocations, _ = parse_report(json.dumps(report), dispatcher=dispatcher)

        assert [i.local_id for i in invocations] == ["01JOBINV0000000000000000AA", "CHILD"]

    def test_a_parent_that_never_appears_is_refused(self, agent_id, dispatcher):
        report = json.loads(_report(dispatcher, agent_id))
        report["invocations"][0]["parent_local_id"] = "NOWHERE"

        with pytest.raises(UnreadableReport, match="NOWHERE"):
            parse_report(json.dumps(report), dispatcher=dispatcher)

    def test_a_cycle_is_refused(self, agent_id, dispatcher):
        report = json.loads(_report(dispatcher, agent_id))
        a = dict(report["invocations"][0], local_id="A", parent_local_id="B")
        b = dict(report["invocations"][0], local_id="B", parent_local_id="A")
        report["invocations"] = [a, b]
        report["model_calls"] = []

        with pytest.raises(UnreadableReport, match="cycle"):
            parse_report(json.dumps(report), dispatcher=dispatcher)


class _Remote(Executor):
    """An executor whose job reports whatever the test scripts."""

    def __init__(self, recorder, report_for):
        super().__init__(recorder)
        self._report_for = report_for

    def _do_dispatch(self, job, *, telemetry):
        return JobHandle(job_id="remote-1")

    def _do_await_result(self, handle):
        return JobResult(job_id=handle.job_id, status="success", artifacts=["build.md"])

    def _do_collect_telemetry(self, handle):
        return self._report_for(handle)


class TestThePollerCollects:
    def _dispatch(self, recorder, agent_id, run_id, executor):
        with recorder.invocation(agent_id, run_id=run_id) as dispatcher:
            descriptor = recorder.descriptor_for(ingest_url="", credential="")
            handle = executor.dispatch(JobSpec(kind="build"), telemetry=descriptor)
        return dispatcher, handle

    def test_a_job_s_work_joins_the_tree_under_its_dispatcher(
        self, recorder, repo, run_id, agent_id
    ):
        executor = _Remote(recorder, lambda h: _report(h.dispatcher, agent_id))
        dispatcher, handle = self._dispatch(recorder, agent_id, run_id, executor)

        result = executor.await_result(handle)

        assert result.status == "success"
        remote = [r for r in repo.invocation_tree(run_id) if r["parent_invocation_id"] == dispatcher]
        assert len(remote) == 1 and remote[0]["depth"] == 1
        call = repo.model_calls_for_run(run_id)[0]
        assert call["agent_invocation_id"] == remote[0]["id"]
        assert call["estimated_cost_usd"] > 0

    def test_collecting_twice_counts_once(self, recorder, repo, run_id, agent_id):
        executor = _Remote(recorder, lambda h: _report(h.dispatcher, agent_id))
        _, handle = self._dispatch(recorder, agent_id, run_id, executor)

        executor.await_result(handle)
        executor.await_result(handle)

        assert len(repo.model_calls_for_run(run_id)) == 1

    def test_a_job_that_reported_nothing_is_not_a_job_that_cost_nothing(
        self, recorder, repo, conn, run_id, agent_id
    ):
        executor = _Remote(recorder, lambda h: None)
        _, handle = self._dispatch(recorder, agent_id, run_id, executor)

        result = executor.await_result(handle)

        assert result.status == "success", "the work product is still returned"
        failures = conn.execute(
            "SELECT signature, message FROM failures WHERE run_id = ?", (run_id,)
        ).fetchall()
        assert [":executor:telemetry:" in f["signature"] for f in failures] == [True]
        assert "unknown, not zero" in failures[0]["message"]
        assert repo.model_calls_for_run(run_id) == []

    def test_an_unreadable_report_ingests_nothing_and_says_why(
        self, recorder, repo, conn, run_id, agent_id
    ):
        executor = _Remote(recorder, lambda h: "{not json")
        _, handle = self._dispatch(recorder, agent_id, run_id, executor)

        executor.await_result(handle)

        failures = conn.execute(
            "SELECT signature FROM failures WHERE run_id = ?", (run_id,)
        ).fetchall()
        assert [":executor:telemetry:" in f["signature"] for f in failures] == [True]
        assert repo.model_calls_for_run(run_id) == []

    def test_ingest_never_opens_a_second_connection(
        self, recorder, repo, run_id, agent_id, monkeypatch
    ):
        """One writer. The test fails if collection reaches for its own
        connection, which is the mistake the design names first."""
        executor = _Remote(recorder, lambda h: _report(h.dispatcher, agent_id))
        _, handle = self._dispatch(recorder, agent_id, run_id, executor)

        def refuse(*_args, **_kwargs):
            raise AssertionError("a second connection was opened")

        monkeypatch.setattr(sqlite3, "connect", refuse)
        executor.await_result(handle)

        assert len(repo.model_calls_for_run(run_id)) == 1

    def test_in_process_work_was_recorded_as_it_ran(self, recorder, conn, run_id, agent_id):
        """The in-process stand-in records its work directly, so there is no
        report to collect and its absence is not a failure."""
        executor = InProcessExecutor(recorder)
        _, handle = self._dispatch(recorder, agent_id, run_id, executor)

        executor.await_result(handle)

        assert conn.execute("SELECT COUNT(*) FROM failures").fetchone()[0] == 0

    def test_every_executor_must_say_how_its_telemetry_returns(self, recorder):
        class Silent(Executor):
            def _do_dispatch(self, job, *, telemetry):
                return JobHandle(job_id="x")

            def _do_await_result(self, handle):
                return JobResult(job_id="x", status="success")

        with pytest.raises(TypeError, match="_do_collect_telemetry"):
            Silent(recorder)


def test_the_in_process_sentinel_is_not_a_report():
    """A sentinel rather than an empty string, so "nothing came back" and
    "nothing needed to" cannot be confused."""
    assert RECORDED_IN_PROCESS is not None and not isinstance(RECORDED_IN_PROCESS, str)
