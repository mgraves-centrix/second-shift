"""Payload capture: what a model call said, kept beside what it cost.

`insert_model_call_payload` existed from the first migration and had no caller,
so six real nights and the first scored eval run on the always-on machine left
no prompt or completion behind. A refused judgement there could be described
only by the character offset its parser died at. These tests are the caller's
contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from secondshift import config
from secondshift.providers.base import Message, RawCompletion, Reasoner
from secondshift.telemetry.payloads import ENV_PAYLOADS, payload_root


class _Fixed(Reasoner):
    """A backend that answers one thing, so the test reads the capture, not a model."""

    provider_kind = "local-vllm"

    def __init__(self, recorder, *, text="the answer", finish_reason="stop"):
        super().__init__(recorder, model="fixed")
        self._text = text
        self._finish_reason = finish_reason

    def _do_complete(self, messages, *, effort):
        return RawCompletion(
            text=self._text,
            prompt_tokens=5,
            completion_tokens=2,
            finish_reason=self._finish_reason,
        )


ASKED = [Message("system", "be brief"), Message("user", "an idea")]


def _complete(recorder, agent_id, run_id, backend=None, **kwargs):
    backend = backend or _Fixed(recorder)
    with recorder.invocation(agent_id, run_id=run_id):
        return backend.complete(ASKED, policy="local-only", **kwargs)


class TestEveryCompletionKeepsWhatItSaid:
    def test_the_prompt_and_the_completion_land_with_a_row(
        self, recorder, repo, run_id, agent_id
    ):
        completion = _complete(recorder, agent_id, run_id)

        row = repo.payload_for(completion.model_call_id)
        assert row is not None
        root = payload_root()
        prompt = json.loads((root / row["prompt_path"]).read_text())
        answer = json.loads((root / row["completion_path"]).read_text())
        assert prompt["messages"] == [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "an idea"},
        ]
        assert answer["text"] == "the answer"

    def test_paths_are_relative_and_sizes_are_read_back_from_disk(
        self, recorder, repo, run_id, agent_id
    ):
        """Relative for the reason artifact paths are: the judge instance runs
        this code against a different root, and an absolute path in a row pins
        a home directory into data. Sizes from the file as written, never from
        the string that was meant to be written."""
        completion = _complete(recorder, agent_id, run_id)

        row = repo.payload_for(completion.model_call_id)
        root = payload_root()
        for column in ("prompt_path", "completion_path"):
            assert not Path(row[column]).is_absolute()
        assert row["prompt_bytes"] == (root / row["prompt_path"]).stat().st_size
        assert row["completion_bytes"] == (root / row["completion_path"]).stat().st_size

    def test_a_completion_that_did_not_finish_keeps_why(
        self, recorder, repo, run_id, agent_id
    ):
        """A truncated judgement is refused before it is parsed. Without the
        reason beside the text, a refusal read back later would look like a
        model that wrote half an answer on purpose."""
        backend = _Fixed(recorder, text="{\"scores\": {", finish_reason="length")

        completion = _complete(recorder, agent_id, run_id, backend)

        row = repo.payload_for(completion.model_call_id)
        answer = json.loads((payload_root() / row["completion_path"]).read_text())
        assert answer["finish_reason"] == "length"

    def test_a_redacted_prompt_is_marked_as_one(self, recorder, repo, run_id, agent_id):
        completion = _complete(recorder, agent_id, run_id, redaction_applied=True)

        assert repo.payload_for(completion.model_call_id)["redacted"] == 1

    def test_a_call_with_no_payload_reads_as_none(self, repo):
        assert repo.payload_for("no-such-call") is None


class TestAFailedWriteDoesNotCostTheAnswer:
    def test_an_unwritable_root_records_a_failure_and_keeps_the_completion(
        self, recorder, repo, conn, run_id, agent_id, tmp_path, monkeypatch
    ):
        """The model call happened and its answer is usable. Losing the night
        to a full disk under the payload directory would turn a telemetry
        failure into a product failure; losing the text silently would be the
        defect this file exists for. So: the answer, a failure row naming why
        the text is missing, and no payload row pointing at nothing."""
        blocker = tmp_path / "not-a-directory"
        blocker.write_text("a file where the payload root should be")
        monkeypatch.setenv(ENV_PAYLOADS, str(blocker))

        completion = _complete(recorder, agent_id, run_id)

        assert completion.text == "the answer"
        assert repo.payload_for(completion.model_call_id) is None
        scopes = [
            r["signature"].split(":")[1]
            for r in conn.execute("SELECT signature FROM failures")
        ]
        assert scopes == ["payload"]


class TestTheRootIsConfiguredAndIsolated:
    def test_tests_never_write_into_a_home_directory(self, tmp_path):
        """Autouse in conftest, as the artifact root is. On the always-on
        machine a test run would otherwise deposit fixtures among real
        payloads, which is where a training set would later be drawn from."""
        assert payload_root() == tmp_path / "payloads"

    def test_the_root_is_a_registered_setting(self):
        setting = config.by_name(ENV_PAYLOADS)
        assert setting.required

    def test_the_default_sits_beside_the_database(self, monkeypatch):
        monkeypatch.delenv(ENV_PAYLOADS, raising=False)
        root = payload_root()
        assert root.name == "payloads"
        assert root.parent == config._default_db_path().parent

    def test_configuration_reports_where_it_resolved(self):
        rows = {r.setting.name: r for r in config.resolve_all()}
        assert rows[ENV_PAYLOADS].value == str(payload_root())


@pytest.mark.parametrize("text", ["plain", "with \"quotes\" and {braces}", "ünïcødé"])
def test_text_round_trips_exactly(text, recorder, repo, run_id, agent_id):
    """JSON on disk, and read back byte-for-byte as the model wrote it. A
    judgement that failed to parse is diagnosed from exactly these bytes."""
    completion = _complete(recorder, agent_id, run_id, _Fixed(recorder, text=text))

    row = repo.payload_for(completion.model_call_id)
    answer = json.loads((payload_root() / row["completion_path"]).read_text())
    assert answer["text"] == text
