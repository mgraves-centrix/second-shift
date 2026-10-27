"""Telemetry: the invocation tree, cost, failures, and external attribution."""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from secondshift.telemetry import context as ctx
from secondshift.telemetry.payloads import (
    PayloadWriteFailed,
    relative_paths,
    write_payload,
)
from secondshift.telemetry.failures import BadOutput, FailureType, classify, signature
from secondshift.telemetry.pricing import MissingRate, PricingTable, Rate
from secondshift.telemetry.recorder import (
    ExternalInvocation,
    ExternalModelCall,
    UnknownDispatcher,
)


class TestInvocationTree:
    def test_nested_invocations_record_depth_and_parentage(
        self, recorder, repo, run_id, agent_id
    ):
        with recorder.invocation(agent_id, run_id=run_id) as root:
            with recorder.invocation(agent_id) as middle:
                with recorder.invocation(agent_id) as leaf:
                    pass

        rows = {r["id"]: r for r in repo.invocation_tree(run_id)}
        assert len(rows) == 3
        assert rows[root]["depth"] == 0 and rows[root]["parent_invocation_id"] is None
        assert rows[middle]["depth"] == 1
        assert rows[middle]["parent_invocation_id"] == root
        assert rows[leaf]["depth"] == 2
        assert rows[leaf]["parent_invocation_id"] == middle

    def test_run_id_inherits_from_parent(self, recorder, repo, run_id, agent_id):
        with recorder.invocation(agent_id, run_id=run_id):
            with recorder.invocation(agent_id) as child:
                pass
        assert repo.get_invocation(child)["run_id"] == run_id

    def test_context_is_restored_after_exit(self, recorder, run_id, agent_id):
        assert ctx.current() is None
        with recorder.invocation(agent_id, run_id=run_id):
            assert ctx.current() is not None
        assert ctx.current() is None

    def test_every_invocation_is_closed(self, recorder, repo, run_id, agent_id):
        with recorder.invocation(agent_id, run_id=run_id):
            with recorder.invocation(agent_id):
                pass
        assert all(r["ended_at_ms"] is not None for r in repo.invocation_tree(run_id))

    async def test_concurrent_siblings_share_a_parent(
        self, recorder, repo, run_id, agent_id
    ):
        async def child(_: int) -> str:
            with recorder.invocation(agent_id) as cid:
                await asyncio.sleep(0)
                return cid

        with recorder.invocation(agent_id, run_id=run_id) as parent:
            children = await asyncio.gather(*(child(i) for i in range(3)))

        rows = {r["id"]: r for r in repo.invocation_tree(run_id)}
        assert len(children) == 3
        for cid in children:
            assert rows[cid]["parent_invocation_id"] == parent
            assert rows[cid]["depth"] == 1
        # No sibling adopted another sibling.
        assert not set(children) & {rows[c]["parent_invocation_id"] for c in children}

    def test_threaded_work_needs_propagate(self, recorder, repo, run_id, agent_id):
        """The documented sharp edge, asserted rather than trusted."""

        def work() -> str:
            with recorder.invocation(agent_id) as cid:
                return cid

        with ThreadPoolExecutor(max_workers=2) as pool:
            with recorder.invocation(agent_id, run_id=run_id) as parent:
                wrapped = pool.submit(ctx.propagate(work)).result()
                bare = pool.submit(work).result()

        rows = {r["id"]: r for r in repo.invocation_tree(run_id)}
        assert rows[wrapped]["parent_invocation_id"] == parent
        # Without propagate() the worker starts from an empty context.
        assert repo.get_invocation(bare)["parent_invocation_id"] is None


class TestFailures:
    def test_raising_invocation_closes_failed_and_records(
        self, recorder, repo, run_id, agent_id, conn
    ):
        with pytest.raises(TimeoutError):
            with recorder.invocation(agent_id, run_id=run_id, stage="research") as iid:
                raise TimeoutError("read timed out after 60s")

        row = repo.get_invocation(iid)
        assert row["outcome"] == "failed"
        assert row["ended_at_ms"] is not None

        failure = conn.execute(
            "SELECT * FROM failures WHERE agent_invocation_id = ?", (iid,)
        ).fetchone()
        assert failure["type"] == FailureType.MODEL_TIMEOUT
        assert "60s" in failure["message"]

    def test_parent_survives_a_failing_child(self, recorder, repo, run_id, agent_id):
        with recorder.invocation(agent_id, run_id=run_id) as parent:
            with pytest.raises(BadOutput):
                with recorder.invocation(agent_id):
                    raise BadOutput("critique rejected the draft")

        assert repo.get_invocation(parent)["outcome"] == "success"

    def test_message_beats_exception_type(self):
        assert classify(RuntimeError("CUDA out of memory")) is FailureType.OOM
        assert classify(BadOutput("rejected")) is FailureType.BAD_OUTPUT
        assert classify(ValueError("something novel")) is FailureType.ORCHESTRATOR_CRASH

    def test_signature_is_stable_across_volatile_detail(self):
        a = signature(FailureType.OOM, RuntimeError("oom at 0x7fff after 12.5s"))
        b = signature(FailureType.OOM, RuntimeError("oom at 0x1234 after 99.9s"))
        assert a == b

    def test_signature_separates_genuinely_different_failures(self):
        a = signature(FailureType.OOM, RuntimeError("cuda out of memory"))
        b = signature(FailureType.OOM, RuntimeError("host out of memory"))
        assert a != b


class TestCost:
    def test_known_rate_is_applied(self, recorder, repo, run_id, agent_id):
        with recorder.invocation(agent_id, run_id=run_id):
            recorder.record_model_call(
                provider="token-factory",
                model="nemotron-3-super",
                policy="cloud-assisted",
                prompt_tokens=1_000_000,
                completion_tokens=1_000_000,
            )
        call = repo.model_calls_for_run(run_id)[0]
        assert call["estimated_cost_usd"] == pytest.approx(4.0)
        assert call["total_tokens"] == 2_000_000

    def test_local_calls_are_free(self, recorder, repo, run_id, agent_id):
        with recorder.invocation(agent_id, run_id=run_id):
            recorder.record_model_call(
                provider="local-vllm",
                model="nemotron-3.5-lightning",
                policy="local-only",
                prompt_tokens=500_000,
                completion_tokens=500_000,
            )
        assert repo.model_calls_for_run(run_id)[0]["estimated_cost_usd"] == 0.0

    def test_missing_rate_fails_loudly(self, recorder, run_id, agent_id):
        with recorder.invocation(agent_id, run_id=run_id):
            with pytest.raises(MissingRate):
                recorder.record_model_call(
                    provider="token-factory",
                    model="a-model-with-no-rate",
                    policy="cloud-assisted",
                    prompt_tokens=10,
                )

    def test_missing_rate_records_nothing(self, recorder, repo, run_id, agent_id):
        with recorder.invocation(agent_id, run_id=run_id):
            with pytest.raises(MissingRate):
                recorder.record_model_call(
                    provider="token-factory",
                    model="unpriced",
                    policy="cloud-assisted",
                    prompt_tokens=10,
                )
        assert repo.model_calls_for_run(run_id) == []

    def test_later_rate_does_not_change_recorded_costs(self):
        table = PricingTable(
            [
                Rate("token-factory", "m", 1_000, 1.0, 1.0),
                Rate("token-factory", "m", 5_000, 9.0, 9.0),
            ]
        )
        early = table.cost_usd(
            provider="token-factory",
            model="m",
            ts_ms=2_000,
            prompt_tokens=1_000_000,
            completion_tokens=0,
        )
        late = table.cost_usd(
            provider="token-factory",
            model="m",
            ts_ms=6_000,
            prompt_tokens=1_000_000,
            completion_tokens=0,
        )
        assert early == pytest.approx(1.0)
        assert late == pytest.approx(9.0)

    def test_exact_model_beats_wildcard(self):
        table = PricingTable(
            [
                Rate("p", "*", 0, 1.0, 1.0),
                Rate("p", "specific", 0, 2.0, 2.0),
            ]
        )
        assert table.rate_for("p", "specific", 10).prompt_usd_per_mtok == 2.0
        assert table.rate_for("p", "other", 10).prompt_usd_per_mtok == 1.0


class TestExternalAttribution:
    def test_remote_work_attaches_under_its_dispatcher(
        self, recorder, repo, run_id, agent_id
    ):
        with recorder.invocation(agent_id, run_id=run_id) as dispatcher:
            pass

        mapping = recorder.ingest_external(
            dispatcher,
            invocations=[ExternalInvocation(local_id="builder", agent_id=agent_id)],
            model_calls=[
                ExternalModelCall(
                    parent_local_id="builder",
                    provider="local-vllm",
                    model="nemotron",
                    policy="cloud-assisted",
                    compute_profile="cloud",
                    prompt_tokens=100,
                    completion_tokens=50,
                )
            ],
        )
        remote = repo.get_invocation(mapping["builder"])
        assert remote["parent_invocation_id"] == dispatcher
        assert remote["depth"] == 1
        assert repo.model_calls_for_run(run_id)[0]["agent_invocation_id"] == remote["id"]

    def test_nested_remote_work_keeps_depth(self, recorder, repo, run_id, agent_id):
        with recorder.invocation(agent_id, run_id=run_id) as dispatcher:
            pass
        mapping = recorder.ingest_external(
            dispatcher,
            invocations=[
                ExternalInvocation(local_id="a", agent_id=agent_id),
                ExternalInvocation(local_id="b", agent_id=agent_id, parent_local_id="a"),
            ],
        )
        assert repo.get_invocation(mapping["b"])["depth"] == 2

    def test_five_concurrent_dispatchers_stay_distinct(
        self, recorder, repo, run_id, agent_id
    ):
        dispatchers = []
        for _ in range(5):
            with recorder.invocation(agent_id, run_id=run_id) as did:
                dispatchers.append(did)

        for index, dispatcher in enumerate(dispatchers):
            mapping = recorder.ingest_external(
                dispatcher,
                invocations=[
                    ExternalInvocation(local_id=f"variant-{index}", agent_id=agent_id)
                ],
            )
            recorded = repo.get_invocation(mapping[f"variant-{index}"])
            assert recorded["parent_invocation_id"] == dispatcher

    def test_unknown_dispatcher_is_rejected(self, recorder, repo, run_id, agent_id):
        before = len(repo.invocation_tree(run_id))
        with pytest.raises(UnknownDispatcher):
            recorder.ingest_external(
                "01JZZZNOTAREALINVOCATION00",
                invocations=[ExternalInvocation(local_id="x", agent_id=agent_id)],
            )
        assert len(repo.invocation_tree(run_id)) == before

    def test_descriptor_requires_an_active_invocation(self, recorder):
        with pytest.raises(RuntimeError, match="outside an invocation"):
            recorder.descriptor_for(ingest_url="https://x", credential="t")

    def test_descriptor_names_the_dispatching_invocation(
        self, recorder, run_id, agent_id
    ):
        with recorder.invocation(agent_id, run_id=run_id) as iid:
            descriptor = recorder.descriptor_for(
                ingest_url="https://ingest.example.invalid/telemetry", credential="token"
            )
        assert descriptor.dispatching_invocation_id == iid
        assert descriptor.run_id == run_id


class TestTimelineRendering:
    def test_timeline_renders_from_scalar_columns(
        self, recorder, repo, run_id, agent_id
    ):
        with recorder.invocation(agent_id, run_id=run_id):
            recorder.record_event(
                lane="researcher",
                kind="search",
                label="tavily: grace blackwell vllm",
                duration_ms=1400,
                payload_json='{"results": 12}',
            )
            recorder.record_event(lane="builder", kind="file_write", label="wrote spec.md")

        rows = repo.timeline(run_id)
        assert len(rows) == 2
        assert "payload_json" not in rows[0].keys()
        assert [r["lane"] for r in rows] == ["researcher", "builder"]
        # duration distinguishes a bar from a tick without any parsing
        assert rows[0]["duration_ms"] == 1400 and rows[1]["duration_ms"] is None


class TestThePayloadStore:
    """The path convention and the write, without a recorder or a database.

    `model_call_payloads` had a complete inserter and no caller for seven weeks,
    so the table was empty after six real nights — the defect this closes. These
    tests are over the store alone; that it is reached from every completion is
    `TestRetentionCannotBeSkipped` in `test_providers.py`.
    """

    def test_the_two_paths_differ_only_in_what_they_hold(self):
        prompt, completion = relative_paths("01J9Z", 1_760_000_000_000)

        assert prompt.endswith(".prompt.json")
        assert completion.endswith(".completion.json")
        assert prompt.removesuffix(".prompt.json") == completion.removesuffix(
            ".completion.json"
        )

    def test_the_month_comes_from_the_call_not_the_clock(self):
        """Externally-attributed telemetry arrives after the fact and carries
        its own timestamp. Filing it under the month it is written would put
        last night's work in next month's directory at a boundary."""
        october, _ = relative_paths("01J9Z", 1_760_000_000_000)
        january, _ = relative_paths("01J9Z", 1_767_225_600_000)

        assert october.startswith("2025-10/")
        assert january.startswith("2026-01/")

    def test_the_stored_path_is_relative(self):
        """The judge instance runs this code against another root, and an
        absolute path in a row pins one machine's home directory into data a
        judge reads — which `scripts/check-no-environment.sh` exists because of."""
        for path in relative_paths("01J9Z", 1_760_000_000_000):
            assert not Path(path).is_absolute()
            assert not path.startswith("~")

    def test_the_prompt_file_holds_every_message(self, tmp_path):
        retained = write_payload(
            model_call_id="01J9Z",
            ts_ms=1_760_000_000_000,
            prompt=[{"role": "user", "content": "score this"}],
            completion={"text": "4", "finish_reason": "stop"},
            root=tmp_path,
        )

        written = json.loads((tmp_path / retained.prompt_path).read_text())
        assert written == [{"role": "user", "content": "score this"}]
        assert json.loads((tmp_path / retained.completion_path).read_text()) == {
            "text": "4",
            "finish_reason": "stop",
        }

    def test_the_byte_counts_are_read_back_not_predicted(self, tmp_path):
        """A count derived from the text passed in proves what was meant rather
        than what landed. The files are JSON with separators and indentation, so
        a count of the original string cannot accidentally agree."""
        retained = write_payload(
            model_call_id="01J9Z",
            ts_ms=1_760_000_000_000,
            prompt=[{"role": "user", "content": "x"}],
            completion={"text": "y"},
            root=tmp_path,
        )

        assert retained.prompt_bytes == len(
            (tmp_path / retained.prompt_path).read_bytes()
        )
        assert retained.completion_bytes == len(
            (tmp_path / retained.completion_path).read_bytes()
        )
        assert retained.prompt_bytes > len("x")

    def test_a_root_that_cannot_be_written_raises_before_any_row(self, tmp_path):
        """Raised rather than returned, so that the one caller decides what a
        lost payload costs. A row pointing at a file that is not there records a
        provenance nobody can check."""
        blocked = tmp_path / "file"
        blocked.write_text("not a directory")

        with pytest.raises(PayloadWriteFailed, match="could not retain"):
            write_payload(
                model_call_id="01J9Z",
                ts_ms=1_760_000_000_000,
                prompt=[],
                completion={},
                root=blocked,
            )


class TestRetainingWhatACallSaid:
    """The recorder's half: the row, the synthetic exclusion, and the failure.

    That retention happens on every completion is `TestRetentionCannotBeSkipped`
    in `test_providers.py`. These drive the recorder directly, which is also the
    only way to reach the synthetic and failed-write cases — `Reasoner.complete`
    passes neither.
    """

    def test_the_row_points_at_the_files_and_counts_their_bytes(
        self, recorder, repo, run_id, agent_id
    ):
        with recorder.invocation(agent_id, run_id=run_id):
            call_id = recorder.record_model_call(
                provider="local-vllm", model="m", policy="local-only"
            )
            retained = recorder.record_model_call_payload(
                model_call_id=call_id,
                prompt=[{"role": "user", "content": "an idea"}],
                completion={"text": "a brief"},
            )

        row = repo.connection.execute(
            "SELECT * FROM model_call_payloads WHERE model_call_id = ?", (call_id,)
        ).fetchone()
        assert row["prompt_path"] == retained.prompt_path
        assert row["completion_path"] == retained.completion_path
        assert row["prompt_bytes"] == retained.prompt_bytes
        assert row["completion_bytes"] == retained.completion_bytes
        assert row["captured_at_ms"] > 0

    def test_synthetic_content_is_never_trainable(
        self, recorder, repo, run_id, agent_id
    ):
        """This table has no `is_synthetic` column, so `training_eligible` is
        where the exclusion lives — the schema designates it for exactly that.
        Seed data reaching a training set is the contamination `is_synthetic`
        exists to prevent, one table further on."""
        with recorder.invocation(agent_id, run_id=run_id):
            real = recorder.record_model_call(
                provider="local-vllm", model="m", policy="local-only"
            )
            recorder.record_model_call_payload(
                model_call_id=real, prompt=[], completion={}
            )
            seeded = recorder.record_model_call(
                provider="local-vllm", model="m", policy="local-only",
                is_synthetic=True,
            )
            recorder.record_model_call_payload(
                model_call_id=seeded, prompt=[], completion={}, is_synthetic=True
            )

        eligible = dict(
            repo.connection.execute(
                "SELECT model_call_id, training_eligible FROM model_call_payloads"
            ).fetchall()
        )
        assert eligible[real] == 1
        assert eligible[seeded] == 0

    def test_redaction_is_recorded_not_inferred(
        self, recorder, repo, run_id, agent_id
    ):
        """So a reader can tell raw captured content from what was prepared for
        egress. `Reasoner.complete` already carries the flag."""
        with recorder.invocation(agent_id, run_id=run_id):
            raw = recorder.record_model_call(
                provider="local-vllm", model="m", policy="local-only"
            )
            recorder.record_model_call_payload(
                model_call_id=raw, prompt=[], completion={}
            )
            prepared = recorder.record_model_call(
                provider="token-factory", model="nemotron-3-super",
                policy="cloud-assisted",
            )
            recorder.record_model_call_payload(
                model_call_id=prepared, prompt=[], completion={},
                redaction_applied=True,
            )

        redacted = dict(
            repo.connection.execute(
                "SELECT model_call_id, redacted FROM model_call_payloads"
            ).fetchall()
        )
        assert redacted[raw] == 0
        assert redacted[prepared] == 1

    def test_a_failed_write_costs_the_evidence_and_nothing_else(
        self, recorder, repo, run_id, agent_id, monkeypatch, tmp_path
    ):
        """The completion is the product and this is evidence about it, so a
        full disk at 2am must cost the evidence alone. Loud, though: a typed
        failure is recorded, and no row points at a file that is not there."""
        blocked = tmp_path / "not-a-directory"
        blocked.write_text("in the way")
        monkeypatch.setenv("SECOND_SHIFT_PAYLOADS", str(blocked))

        with recorder.invocation(agent_id, run_id=run_id):
            call_id = recorder.record_model_call(
                provider="local-vllm", model="m", policy="local-only"
            )
            retained = recorder.record_model_call_payload(
                model_call_id=call_id, prompt=[], completion={}
            )

        assert retained is None
        assert len(repo.model_calls_for_run(run_id)) == 1, "the cost row was lost"
        assert repo.connection.execute(
            "SELECT count(*) FROM model_call_payloads"
        ).fetchone()[0] == 0, "a row points at a file that is not there"
        failures = repo.connection.execute(
            "SELECT type, signature, message FROM failures"
        ).fetchall()
        assert len(failures) == 1, "the gap is silent"
        assert "retain:payload" in failures[0]["signature"]

    def test_a_night_is_not_lost_to_its_own_evidence(
        self, recorder, repo, run_id, agent_id, monkeypatch, tmp_path
    ):
        """The same case through a provider, which is where it would actually
        happen: the stage continues and the caller still gets its text."""
        from secondshift.providers.base import Message, RawCompletion, Reasoner

        class Backend(Reasoner):
            provider_kind = "local-vllm"

            def _do_complete(self, messages, *, effort):
                return RawCompletion(text="the brief survives")

        blocked = tmp_path / "in-the-way"
        blocked.write_text("not a directory")
        monkeypatch.setenv("SECOND_SHIFT_PAYLOADS", str(blocked))

        with recorder.invocation(agent_id, run_id=run_id):
            completion = Backend(recorder, model="m").complete(
                [Message("user", "x")], policy="local-only"
            )

        assert completion.text == "the brief survives"
        assert len(repo.model_calls_for_run(run_id)) == 1
        assert repo.connection.execute(
            "SELECT count(*) FROM failures"
        ).fetchone()[0] == 1
