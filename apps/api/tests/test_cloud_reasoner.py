"""The cloud reasoner: Token Factory, under `cloud-assisted` only.

The system's first remote reasoner. Two guards already stood between it and a
`local-only` idea — the airlock at the call and the `model_calls` CHECK at the
database — and neither changes here. What is new is a credential, which is read
when a call is made, sent only as the bearer token, and never written anywhere
the call is recorded.
"""

from __future__ import annotations

import pytest

from secondshift import config
from secondshift.airlock.policy import AirlockViolation
from secondshift.providers.base import Message
from secondshift.providers.registry import Registry
from secondshift.providers.tokenfactory import (
    CloudReasonerNotConfigured,
    CloudReasonerUnavailable,
    TokenFactoryReasoner,
)
from secondshift.telemetry.pricing import PricingTable

KEY = "tf-test-key-not-a-real-one"
MODEL = "nvidia/nemotron-3-super-120b-a12b"


@pytest.fixture
def recorder(repo):
    """On the real rate table: the identifiers it prices are the point here."""
    from secondshift.telemetry.recorder import Recorder

    return Recorder(repo, pricing=PricingTable.load(), compute_profile="spark")


@pytest.fixture
def cloud(vllm_stub, monkeypatch, recorder):
    monkeypatch.setenv(config.ENV_NEBIUS_KEY, KEY)
    settings = config.CloudReasonerSettings(
        base_url=f"http://{vllm_stub.host}:{vllm_stub.port}/v1",
        model=MODEL,
        max_tokens=512,
        temperature=0.6,
        timeout_s=5.0,
    )
    return TokenFactoryReasoner(recorder, settings=settings)


def _ask(reasoner, recorder, agent_id, run_id, policy="cloud-assisted"):
    with recorder.invocation(agent_id, run_id=run_id):
        return reasoner.complete([Message("user", "a synthetic question")], policy=policy)


class TestItIsTheRemoteReasoner:
    def test_a_completion_is_recorded_as_token_factory_with_its_cost(
        self, cloud, recorder, repo, run_id, agent_id, vllm_stub
    ):
        vllm_stub.answers(text="an answer", prompt_tokens=1_000_000, completion_tokens=1_000_000)

        completion = _ask(cloud, recorder, agent_id, run_id)

        assert completion.text == "an answer"
        call = repo.model_calls_for_run(run_id)[0]
        assert (call["provider"], call["model"], call["policy"]) == (
            "token-factory", MODEL, "cloud-assisted",
        )
        assert call["estimated_cost_usd"] == pytest.approx(0.30 + 0.90)

    def test_the_request_names_the_served_model(self, cloud, recorder, run_id, agent_id, vllm_stub):
        _ask(cloud, recorder, agent_id, run_id)

        assert vllm_stub.requests[0]["model"] == MODEL
        assert vllm_stub.requests[0]["messages"] == [
            {"role": "user", "content": "a synthetic question"}
        ]


class TestTheAirlockHolds:
    def test_local_only_is_refused_before_anything_is_sent(
        self, cloud, recorder, repo, run_id, agent_id, vllm_stub
    ):
        with pytest.raises(AirlockViolation):
            _ask(cloud, recorder, agent_id, run_id, policy="local-only")

        assert vllm_stub.requests == []
        assert repo.model_calls_for_run(run_id) == []


class TestTheCredential:
    def test_it_travels_only_as_the_bearer_token(self, cloud, recorder, run_id, agent_id, vllm_stub):
        _ask(cloud, recorder, agent_id, run_id)

        assert vllm_stub.headers[0]["authorization"] == f"Bearer {KEY}"
        assert KEY not in str(vllm_stub.requests[0])

    def test_a_refusal_from_the_server_does_not_carry_the_key(
        self, cloud, recorder, conn, run_id, agent_id, vllm_stub
    ):
        vllm_stub.fails(401, f"bad token {KEY}")

        with pytest.raises(CloudReasonerUnavailable) as raised:
            _ask(cloud, recorder, agent_id, run_id)

        assert KEY not in str(raised.value)
        recorded = " ".join(r["message"] for r in conn.execute("SELECT message FROM failures"))
        assert KEY not in recorded
        assert "401" in recorded

    def test_no_key_is_a_refusal_not_a_substitute(
        self, cloud, recorder, run_id, agent_id, vllm_stub, monkeypatch
    ):
        monkeypatch.delenv(config.ENV_NEBIUS_KEY)

        with pytest.raises(CloudReasonerNotConfigured, match=config.ENV_NEBIUS_KEY):
            _ask(cloud, recorder, agent_id, run_id)

        assert vllm_stub.requests == []

    def test_the_key_is_a_registered_secret(self, monkeypatch):
        monkeypatch.setenv(config.ENV_NEBIUS_KEY, KEY)
        rows = {r.setting.name: r for r in config.resolve_all()}

        assert config.by_name(config.ENV_NEBIUS_KEY).secret
        assert rows[config.ENV_NEBIUS_KEY].display == config.REDACTED


class TestTheCloudProfileBindsIt:
    def test_the_echo_is_gone(self, recorder, monkeypatch):
        """The `cloud` profile bound `EchoReasoner` as a placeholder: a model
        call recorded, the prompt returned, nothing reasoned. It is replaced by
        the real backend, which refuses when it cannot run rather than echoing."""
        monkeypatch.delenv(config.ENV_NEBIUS_KEY, raising=False)

        reasoner = Registry(recorder).bind("cloud").reasoner

        assert isinstance(reasoner, TokenFactoryReasoner)
        assert reasoner.model == config.cloud_reasoner_settings().model


class TestTheRatesAreForTheIdsThatAreServed:
    def test_every_configured_cloud_model_has_a_standard_rate(self):
        """On 17 Oct `/v1/models` showed the rate table keyed by console
        display names the API does not serve. A call to the configured model
        must price, or the cost curve would have a hole exactly where the cloud
        night is."""
        table = PricingTable.load()
        model = config.cloud_reasoner_settings().model

        assert table.cost_usd(
            provider="token-factory", model=model, ts_ms=1_792_000_000_000,
            prompt_tokens=1_000_000, completion_tokens=0,
        ) > 0
        assert not model.endswith("-Batch"), "Batch is unavailable; the standard rate applies"


def test_a_cloud_night_s_cost_reads_off_the_view(cloud, recorder, conn, run_id, agent_id, vllm_stub):
    """Without arithmetic: the demo's side-by-side reads `night_totals`."""
    vllm_stub.answers(prompt_tokens=1_000_000, completion_tokens=0)

    _ask(cloud, recorder, agent_id, run_id)

    row = conn.execute("SELECT cloud_tokens, model_cost_usd FROM night_totals").fetchone()
    assert row["cloud_tokens"] == 1_000_000
    assert row["model_cost_usd"] == pytest.approx(0.30)


def test_reasoning_is_priced_as_the_output_it_is(cloud, recorder, repo, run_id, agent_id, vllm_stub):
    """Token Factory's `completion_tokens` includes the reasoning, and that is
    what it bills: on 17 Oct a call reported 121 completion tokens of which 73
    were reasoning, with `total_tokens` 149 = 28 + 121. The parser splits the
    reasoning out so the recorded total is not counted twice, and the recorder
    then priced only what was left — 48 of 121, on that call. Local rates are
    zero, which is why it never showed."""
    vllm_stub.answers(prompt_tokens=1_000_000, completion_tokens=1_000_000, reasoning_tokens=500_000)

    _ask(cloud, recorder, agent_id, run_id)

    call = repo.model_calls_for_run(run_id)[0]
    assert call["total_tokens"] == 2_000_000, "the total is still counted once"
    assert call["estimated_cost_usd"] == pytest.approx(0.30 + 0.90)
