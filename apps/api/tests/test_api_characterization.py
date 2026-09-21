"""Every route's answer, recorded before the layer was reorganized.

This exists for one change — splitting `api/app.py` into a module per capability
— and is worth keeping after it, because the question it answers ("did moving
this change what it returns?") is asked by every future change to the layer.

`characterize.py` builds the world and takes the record. This file only compares
against `fixtures/api_characterization.json`, and nothing here can rewrite it.
"""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from secondshift.api import schemas

from .characterize import GOLDEN, build_world, capture, normalize_json


@pytest.fixture(scope="module")
def golden() -> dict:
    return json.loads(GOLDEN.read_text())


@pytest.fixture(scope="module")
def captured(tmp_path_factory) -> dict:
    """One night, one capture, shared by every case.

    Module-scoped because generating the night and answering twenty-three
    requests — one of them a quarter-megabyte timeline — is the expensive part,
    and every case reads the same capture.
    """
    client, world = build_world(tmp_path_factory.mktemp("characterize"))
    return capture(client, world)


def _case_names() -> list[str]:
    return sorted(json.loads(GOLDEN.read_text()))


class TestEveryRouteAnswersAsItDid:
    @pytest.mark.parametrize("name", _case_names())
    def test_case(self, name, captured, golden):
        assert captured[name] == golden[name]

    def test_no_case_was_added_or_dropped(self, captured, golden):
        """A case silently removed is a route silently unverified."""
        assert sorted(captured) == sorted(golden)


class TestTheRecordRecordsSomething:
    def test_every_response_model_field_appears(self, golden):
        """A model absent from the record is a model this proves nothing about.

        The first draft of the capture read `/events/1`, whose invocation made
        no model call, so ten fields of `ModelCallResponse` were verified by an
        empty list; and asked a non-synthetic deployment for a briefing about a
        synthetic night, so `nights` came back empty and three more models with
        it. Both were invisible until this was written.
        """
        segments = {
            part
            for case in golden.values()
            for path in case.get("key_paths", [])
            for part in path.replace("[]", "").split(".")
            if part
        }
        uncovered = [
            f"{name}.{field}"
            for name in dir(schemas)
            for model in [getattr(schemas, name)]
            if isinstance(model, type)
            and issubclass(model, BaseModel)
            and model is not BaseModel
            and not name.endswith("Request")
            for field in model.model_fields
            if field not in segments
        ]
        assert uncovered == []

    def test_a_renamed_field_changes_the_record(self):
        before = '{"lane": "research", "ts_ms": 1790006023488}'
        after = '{"lane_name": "research", "ts_ms": 1790006023488}'
        assert normalize_json(before) != normalize_json(after)

    def test_a_changed_value_changes_the_record(self):
        before = '{"lane": "research", "ts_ms": 1790006023488}'
        after = '{"lane": "critique", "ts_ms": 1790006023488}'
        assert normalize_json(before) != normalize_json(after)

    def test_a_reordered_field_changes_the_record(self):
        """Field order is response-model order, so a reorder is a real change."""
        before = '{"lane": "research", "kind": "note"}'
        after = '{"kind": "note", "lane": "research"}'
        assert normalize_json(before) != normalize_json(after)

    def test_a_dropped_field_changes_the_record(self):
        before = '{"lane": "research", "severity": null}'
        after = '{"lane": "research"}'
        assert normalize_json(before) != normalize_json(after)

    def test_a_different_identifier_does_not(self):
        """The other half: what the record deliberately cannot see.

        Two runs of the same seed mint different ULIDs, and a record that failed
        on that would fail every second run for no reason anybody could act on.
        """
        before = '{"id": "01M13BW0B3ESB2KN5YXWZAQVEB"}'
        after = '{"id": "01M145087K6B0QCRBT7FWP0V53"}'
        assert normalize_json(before) == normalize_json(after)

    def test_a_shifted_night_does_not(self):
        """Instants are rebased, so the same night an hour later is the same."""
        before = '{"a_ms": 1790006023488, "b_ms": 1790006025000}'
        after = '{"a_ms": 1790009623488, "b_ms": 1790009625000}'
        assert normalize_json(before) == normalize_json(after)

    def test_a_shifted_night_with_a_different_span_does_not_pass(self):
        """But the spacing between them is data, and survives the rebase."""
        before = '{"a_ms": 1790006023488, "b_ms": 1790006025000}'
        after = '{"a_ms": 1790006023488, "b_ms": 1790006029999}'
        assert normalize_json(before) != normalize_json(after)
