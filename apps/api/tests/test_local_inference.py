"""The local reasoner: what it sends, what it reads back, and how it fails.

Exercised against a stub server on a real socket. The provider is almost entirely
transport and response reading, so a test that patched the transport would cover
everything except the part that can be wrong.
"""

from __future__ import annotations

import json

import pytest

from secondshift import config
from secondshift.airlock.policy import AirlockViolation
from secondshift.config import LocalReasonerSettings
from secondshift.providers.base import Message
from secondshift.providers.registry import LocalReasonerNotConfigured, Registry
from secondshift.providers.vllm import (
    ReasonerTimeout,
    ReasonerUnavailable,
    VllmReasoner,
)
from secondshift.telemetry.failures import BadOutput, FailureType


def _settings(stub, **overrides) -> LocalReasonerSettings:
    base = dict(
        host=stub.host,
        port=stub.port,
        model="stub-served-model",
        max_tokens=256,
        temperature=0.7,
        timeout_s=5.0,
    )
    base.update(overrides)
    return LocalReasonerSettings(**base)


@pytest.fixture
def reasoner(recorder, vllm_stub) -> VllmReasoner:
    return VllmReasoner(recorder, settings=_settings(vllm_stub))


def _failures(repo) -> list[dict]:
    return [dict(r) for r in repo.connection.execute("SELECT * FROM failures")]


class TestTheRequest:
    def test_the_configured_model_and_sampling_are_sent(
        self, reasoner, vllm_stub, run_id, agent_id, recorder
    ):
        with recorder.invocation(agent_id, run_id=run_id):
            reasoner.complete([Message("user", "an idea")], policy="local-only")

        sent = vllm_stub.requests[0]
        assert sent["model"] == "stub-served-model"
        assert sent["messages"] == [{"role": "user", "content": "an idea"}]
        assert sent["max_tokens"] == 256
        assert sent["temperature"] == 0.7
        assert sent["stream"] is False

    def test_effort_is_recorded_but_does_not_change_the_request(
        self, reasoner, vllm_stub, run_id, agent_id, recorder, repo
    ):
        """local-only never escalates, and this profile serves one model."""
        with recorder.invocation(agent_id, run_id=run_id):
            reasoner.complete(
                [Message("user", "an idea")], policy="local-only", effort="deep"
            )

        assert "effort" not in vllm_stub.requests[0]
        assert repo.model_calls_for_run(run_id)[0]["effort"] == "deep"


class TestTheResponse:
    def test_the_answer_and_its_counts_come_from_the_server(
        self, reasoner, vllm_stub, run_id, agent_id, recorder, repo
    ):
        vllm_stub.answers("a real answer", prompt_tokens=31, completion_tokens=17)
        with recorder.invocation(agent_id, run_id=run_id):
            result = reasoner.complete([Message("user", "go")], policy="local-only")

        assert result.text == "a real answer"
        call = repo.model_calls_for_run(run_id)[0]
        assert call["prompt_tokens"] == 31
        assert call["completion_tokens"] == 17
        assert call["provider"] == "local-vllm"
        assert call["model"] == "stub-served-model"

    def test_reasoning_tokens_are_not_counted_twice(
        self, reasoner, vllm_stub, run_id, agent_id, recorder, repo
    ):
        """Usage nests reasoning inside completion; the recorder sums the three."""
        vllm_stub.answers(
            "the answer",
            prompt_tokens=10,
            completion_tokens=90,
            reasoning_tokens=60,
            reasoning_content="a thinking process",
        )
        with recorder.invocation(agent_id, run_id=run_id):
            reasoner.complete([Message("user", "go")], policy="local-only")

        call = repo.model_calls_for_run(run_id)[0]
        assert call["completion_tokens"] == 30
        assert call["reasoning_tokens"] == 60
        assert call["total_tokens"] == 100

    def test_inline_chain_of_thought_is_returned_whole(
        self, reasoner, vllm_stub, run_id, agent_id, recorder
    ):
        """The served model opens with its reasoning when no parser splits it.

        The provider does not guess where reasoning ends. A marker-string
        splitter would delete the answer whenever it guessed wrong, and telemetry
        would then count tokens nobody received.
        """
        emitted = "Here's a thinking process:\nfirst...\n\nThe answer is 42."
        vllm_stub.answers(emitted)
        with recorder.invocation(agent_id, run_id=run_id):
            result = reasoner.complete([Message("user", "go")], policy="local-only")

        assert result.text == emitted

    def test_a_clean_stop_records_no_warning(
        self, reasoner, vllm_stub, run_id, agent_id, recorder, repo
    ):
        with recorder.invocation(agent_id, run_id=run_id):
            reasoner.complete([Message("user", "go")], policy="local-only")
        assert not [e for e in repo.timeline(run_id) if e["severity"] == "warn"]

    def test_truncation_is_visible(
        self, reasoner, vllm_stub, run_id, agent_id, recorder, repo
    ):
        """A brief cut off at the token limit reads exactly like a finished one."""
        vllm_stub.answers("half an ans", finish_reason="length")
        with recorder.invocation(agent_id, run_id=run_id):
            reasoner.complete([Message("user", "go")], policy="local-only")

        warnings = [e for e in repo.timeline(run_id) if e["severity"] == "warn"]
        assert len(warnings) == 1
        assert warnings[0]["kind"] == "model_call"
        assert "length" in warnings[0]["label"]


class TestFailures:
    def test_an_unreachable_endpoint_raises_and_records_a_network_failure(
        self, recorder, repo, vllm_stub, run_id, agent_id
    ):
        port = vllm_stub.port
        vllm_stub.stop()
        reasoner = VllmReasoner(recorder, settings=_settings(vllm_stub, port=port))

        with recorder.invocation(agent_id, run_id=run_id):
            with pytest.raises(ReasonerUnavailable, match=str(port)):
                reasoner.complete([Message("user", "go")], policy="local-only")

        recorded = _failures(repo)
        assert [f["type"] for f in recorded] == [FailureType.NETWORK]
        assert not repo.model_calls_for_run(run_id)

    def test_a_slow_server_raises_a_timeout(
        self, recorder, repo, vllm_stub, run_id, agent_id
    ):
        vllm_stub.delay_s = 0.3
        reasoner = VllmReasoner(recorder, settings=_settings(vllm_stub, timeout_s=0.02))

        with recorder.invocation(agent_id, run_id=run_id):
            with pytest.raises(ReasonerTimeout):
                reasoner.complete([Message("user", "go")], policy="local-only")

        assert [f["type"] for f in _failures(repo)] == [FailureType.MODEL_TIMEOUT]

    def test_an_error_status_carries_the_servers_own_words(
        self, reasoner, vllm_stub, recorder, repo, run_id, agent_id
    ):
        """A 500 saying "out of memory" must land as an OOM, not as a 500."""
        vllm_stub.fails(500, "CUDA out of memory: tried to allocate 2 GiB")

        with recorder.invocation(agent_id, run_id=run_id):
            with pytest.raises(ReasonerUnavailable, match="out of memory"):
                reasoner.complete([Message("user", "go")], policy="local-only")

        assert [f["type"] for f in _failures(repo)] == [FailureType.OOM]

    def test_a_response_that_is_not_a_completion_is_bad_output(
        self, reasoner, vllm_stub, recorder, repo, run_id, agent_id
    ):
        vllm_stub.answers_with(json.dumps({"error": "no idea"}).encode())

        with recorder.invocation(agent_id, run_id=run_id):
            with pytest.raises(BadOutput, match="no choices"):
                reasoner.complete([Message("user", "go")], policy="local-only")

        assert [f["type"] for f in _failures(repo)] == [FailureType.BAD_OUTPUT]

    def test_a_response_that_is_not_json_is_bad_output(
        self, reasoner, vllm_stub, recorder, repo, run_id, agent_id
    ):
        vllm_stub.answers_with(b"<html>gateway timed out</html>")

        with recorder.invocation(agent_id, run_id=run_id):
            with pytest.raises(BadOutput):
                reasoner.complete([Message("user", "go")], policy="local-only")

        assert len(_failures(repo)) == 1

    def test_no_substitute_answer_is_returned(
        self, reasoner, vllm_stub, recorder, repo, run_id, agent_id
    ):
        """A fabricated answer recorded as a model call is indistinguishable
        in the data from a real one, which is the whole reason to raise."""
        vllm_stub.fails(503, "server is loading the model")

        with recorder.invocation(agent_id, run_id=run_id):
            with pytest.raises(ReasonerUnavailable):
                reasoner.complete([Message("user", "go")], policy="local-only")

        assert not repo.model_calls_for_run(run_id)


class TestBinding:
    def test_a_local_profile_binds_the_real_reasoner(self, recorder, local_reasoner_env):
        assert isinstance(Registry(recorder).bind("spark").reasoner, VllmReasoner)
        assert isinstance(Registry(recorder).bind("workstation").reasoner, VllmReasoner)

    def test_cloud_does_not(self, recorder, local_reasoner_env):
        """Binding the cloud reasoner is nebius-executor's, not this one's."""
        assert not isinstance(Registry(recorder).bind("cloud").reasoner, VllmReasoner)

    def test_an_unconfigured_local_profile_is_refused_rather_than_echoed(
        self, recorder, monkeypatch, tmp_path
    ):
        monkeypatch.delenv(config.ENV_LOCAL_MODEL, raising=False)
        monkeypatch.setattr(config, "_MODELS_CONFIG", tmp_path / "absent.toml")
        with pytest.raises(LocalReasonerNotConfigured, match="served-model name"):
            Registry(recorder).bind("spark")

    def test_local_only_is_permitted_because_the_provider_is_local(
        self, reasoner, recorder, run_id, agent_id
    ):
        with recorder.invocation(agent_id, run_id=run_id):
            reasoner.complete([Message("user", "private")], policy="local-only")

    def test_the_provider_is_not_remote(self, reasoner):
        from secondshift.airlock.policy import is_remote

        assert not is_remote(reasoner.provider_kind)


class TestConfiguredSettings:
    def test_the_committed_configuration_is_complete(self):
        settings = config.local_reasoner_settings()
        assert settings.model
        assert settings.port
        assert settings.max_tokens > 0
        assert settings.timeout_s > 0

    def test_sampling_is_not_deterministic(self):
        """`evals` reports a spread; a temperature of zero would report zero."""
        assert config.local_reasoner_settings().temperature > 0


def test_a_remote_provider_is_still_refused_under_local_only(recorder):
    """The airlock is unchanged by a real local backend arriving."""
    from secondshift.providers.base import RawCompletion, Reasoner

    class RemoteReasoner(Reasoner):
        provider_kind = "token-factory"

        def _do_complete(self, messages, *, effort):
            return RawCompletion(text="leaked")

    with pytest.raises(AirlockViolation):
        RemoteReasoner(recorder).complete([Message("user", "x")], policy="local-only")
