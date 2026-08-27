"""Provider interfaces: instrumentation by the base class, and no leakage."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import secondshift
from secondshift.airlock.policy import AirlockViolation
from secondshift.providers.base import (
    JobSpec,
    Message,
    RawCompletion,
    Reasoner,
)
from secondshift.providers.null import InProcessExecutor
from secondshift.providers.registry import Registry

PACKAGE_ROOT = Path(secondshift.__file__).parent
PROVIDERS_DIR = PACKAGE_ROOT / "providers"

# Anything that would tie a non-provider module to one backend.
BANNED_IMPORTS = re.compile(
    r"^\s*(?:from|import)\s+(openai|anthropic|vllm|nemo|nemo_toolkit|transformers"
    r"|torch|tavily|boto3|google\.generativeai)\b",
    re.M,
)
BANNED_MODEL_IDS = re.compile(
    r"nemotron|parakeet|magpie|nv-embed|llama-nemotron|gpt-4|claude-", re.I
)


def _modules_outside_providers() -> list[Path]:
    return [
        p
        for p in PACKAGE_ROOT.rglob("*.py")
        if PROVIDERS_DIR not in p.parents
        and p != PROVIDERS_DIR
        # AppleDouble sidecars match *.py but are binary, not source.
        and not p.name.startswith(".")
    ]


class TestBaseClassOwnsTelemetry:
    def test_implementation_records_without_telemetry_code(
        self, recorder, repo, run_id, agent_id
    ):
        """A new backend overrides one method and is instrumented anyway."""

        class BrandNewBackend(Reasoner):
            provider_kind = "local-vllm"

            def _do_complete(self, messages, *, effort):
                return RawCompletion(text="ok", prompt_tokens=7, completion_tokens=3)

        source = __import__("inspect").getsource(BrandNewBackend)
        assert "record_" not in source and "recorder" not in source

        backend = BrandNewBackend(recorder, model="brand-new")
        with recorder.invocation(agent_id, run_id=run_id):
            completion = backend.complete(
                [Message("user", "hello")], policy="local-only"
            )

        calls = repo.model_calls_for_run(run_id)
        assert len(calls) == 1
        assert calls[0]["prompt_tokens"] == 7
        assert calls[0]["model"] == "brand-new"
        assert calls[0]["latency_ms"] is not None
        assert completion.model_call_id == calls[0]["id"]

    def test_null_providers_contain_no_telemetry_code(self):
        source = (PROVIDERS_DIR / "null.py").read_text()
        assert "record_" not in source

    def test_completion_carries_the_recorded_call_id(
        self, recorder, repo, run_id, agent_id
    ):
        providers = Registry(recorder).bind("spark")
        with recorder.invocation(agent_id, run_id=run_id):
            result = providers.reasoner.complete(
                [Message("user", "an idea")], policy="local-only"
            )
        assert result.model_call_id == repo.model_calls_for_run(run_id)[0]["id"]


class TestAirlockAtCallTime:
    def test_local_only_refuses_a_remote_reasoner(self, recorder, run_id, agent_id):
        class RemoteReasoner(Reasoner):
            provider_kind = "token-factory"

            def _do_complete(self, messages, *, effort):
                raise AssertionError("must not be reached")

        backend = RemoteReasoner(recorder, model="remote")
        with recorder.invocation(agent_id, run_id=run_id):
            with pytest.raises(AirlockViolation):
                backend.complete([Message("user", "secret")], policy="local-only")

    def test_refusal_happens_before_the_call(self, recorder, repo, run_id, agent_id):
        """Nothing is recorded, because nothing was sent."""

        class RemoteReasoner(Reasoner):
            provider_kind = "token-factory"

            def _do_complete(self, messages, *, effort):
                raise AssertionError("must not be reached")

        with recorder.invocation(agent_id, run_id=run_id):
            with pytest.raises(AirlockViolation):
                RemoteReasoner(recorder, model="remote").complete(
                    [Message("user", "x")], policy="local-only"
                )
        assert repo.model_calls_for_run(run_id) == []

    def test_cloud_assisted_permits_a_remote_reasoner(self, recorder, run_id, agent_id):
        class RemoteReasoner(Reasoner):
            provider_kind = "token-factory"

            def _do_complete(self, messages, *, effort):
                return RawCompletion(text="ok", prompt_tokens=1, completion_tokens=1)

        with recorder.invocation(agent_id, run_id=run_id):
            result = RemoteReasoner(recorder, model="nemotron-3-super").complete(
                [Message("user", "x")], policy="cloud-assisted"
            )
        assert result.text == "ok"


class TestExecutorDescriptor:
    def test_dispatch_carries_the_dispatching_invocation(
        self, recorder, run_id, agent_id
    ):
        executor = InProcessExecutor(recorder, model="jobs")
        with recorder.invocation(agent_id, run_id=run_id) as iid:
            descriptor = recorder.descriptor_for(
                ingest_url="https://ingest.example.invalid/ingest", credential="tok"
            )
            handle = executor.dispatch(JobSpec(kind="build"), telemetry=descriptor)

        seen = executor.descriptor_seen(handle.job_id)
        assert seen.dispatching_invocation_id == iid
        assert seen.run_id == run_id
        assert seen.credential == "tok"

    def test_job_result_carries_no_telemetry(self, recorder, run_id, agent_id):
        executor = InProcessExecutor(recorder, model="jobs")
        with recorder.invocation(agent_id, run_id=run_id):
            descriptor = recorder.descriptor_for(ingest_url="https://x", credential="t")
            handle = executor.dispatch(JobSpec(kind="build"), telemetry=descriptor)
            result = executor.await_result(handle)

        fields = set(result.__slots__)
        assert not fields & {"telemetry", "invocations", "model_calls", "events"}
        assert result.status == "success"

    def test_dispatch_records_lifecycle_events(self, recorder, repo, run_id, agent_id):
        executor = InProcessExecutor(recorder, model="jobs")
        with recorder.invocation(agent_id, run_id=run_id):
            descriptor = recorder.descriptor_for(ingest_url="https://x", credential="t")
            handle = executor.dispatch(JobSpec(kind="build"), telemetry=descriptor)
            executor.await_result(handle)

        kinds = [r["kind"] for r in repo.timeline(run_id)]
        assert "job_dispatch" in kinds and "job_complete" in kinds


class TestNoProviderLeakage:
    def test_no_backend_sdk_imported_outside_providers(self):
        offenders = {
            path.relative_to(PACKAGE_ROOT).as_posix(): BANNED_IMPORTS.findall(
                path.read_text()
            )
            for path in _modules_outside_providers()
            if BANNED_IMPORTS.search(path.read_text())
        }
        assert not offenders, f"provider SDK imported outside providers/: {offenders}"

    def test_no_model_identifier_outside_providers(self):
        offenders = {
            path.relative_to(PACKAGE_ROOT).as_posix(): sorted(
                set(BANNED_MODEL_IDS.findall(path.read_text()))
            )
            for path in _modules_outside_providers()
            if BANNED_MODEL_IDS.search(path.read_text())
        }
        assert not offenders, f"model identifiers outside providers/: {offenders}"

    def test_the_scan_actually_covers_something(self):
        """A vacuous scan would pass forever. Assert it has files to check."""
        assert len(_modules_outside_providers()) >= 5
