"""What every route answers today, captured so a refactor can be checked.

This module is the capture; `test_api_characterization.py` is the assertion. The
two are separate so that regenerating the record is something a person runs on
purpose — `python -m tests.characterize`, from `apps/api` — and never something a test run can do
by accident. A golden file a failing test can rewrite is a golden file that
agrees with whatever the code says.

**Why the responses are normalized rather than recorded literally.** The night
this runs against is generated deterministically, but its identifiers are ULIDs
minted from the wall clock and several of its instants are too, so two runs of
the same seed produce the same night with different ids. Recording the bytes
verbatim would produce a record that fails on the second run for reasons that
have nothing to do with the code. So identifiers are replaced by the order they
first appear, instants are rebased against the earliest one in the response, and
the two fields that are a server clock read — `received_at_ms`, `answered_at_ms`
— become a marker.

Nothing else is touched. A renamed field, a dropped field, a changed status, a
changed content type, a changed error message and a reordered list all still
change the record, which is the point. `test_the_record_can_fail` proves it.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from secondshift.telemetry.pricing import PricingTable, Rate

GOLDEN = Path(__file__).resolve().parent / "fixtures" / "api_characterization.json"

#: The night this is captured against.
SEED = 42

#: Fixed rather than loaded, because `/events/{id}` reports an estimated cost and
#: the pricing file is expected to change. The record is of the layer's shape,
#: not of what a token costs this week.
PRICING = PricingTable(
    [
        Rate("local-vllm", "*", 0, 0.0, 0.0),
        Rate("token-factory", "nemotron-3-super", 0, 1.0, 3.0),
    ]
)

#: Crockford base32, 26 characters. Every identifier in this system is one.
_ULID = re.compile(r"\b[0-9A-HJKMNP-TV-Z]{26}\b")

#: Epoch milliseconds for any date this project will plausibly see.
_INSTANT = re.compile(r"\b1[0-9]{12}\b")

#: Read from the server's clock at the moment of the request, so unrepeatable by
#: construction. The contract is that the field is there and carries an instant,
#: not which instant — `test_capture_api.py` asserts the behavior directly.
_CLOCK_FIELDS = ("received_at_ms", "answered_at_ms")


#: An integer at or above this is an instant, not a count and not a duration.
#: Durations here are hundreds of milliseconds and token counts are thousands,
#: so the gap is four orders of magnitude wide and needs no list of field names
#: to stay on the right side of — which matters, because a list of field names
#: is a thing a new field is added without.
_INSTANT_FLOOR = 1_000_000_000_000


def _ulids(text: str, ids: dict[str, str]) -> str:
    return _ULID.sub(lambda m: ids.setdefault(m.group(0), f"<id{len(ids):03d}>"), text)


def _instants(body: Any, found: set[int]) -> None:
    if isinstance(body, dict):
        for k, v in body.items():
            if k not in _CLOCK_FIELDS:
                _instants(v, found)
    elif isinstance(body, list):
        for v in body:
            _instants(v, found)
    elif isinstance(body, str):
        found.update(int(n) for n in _INSTANT.findall(body))
    elif isinstance(body, int) and not isinstance(body, bool) and body >= _INSTANT_FLOOR:
        found.add(body)


def _rewrite(body: Any, ids: dict[str, str], base: int) -> Any:
    if isinstance(body, dict):
        return {
            k: "<clock>" if k in _CLOCK_FIELDS and body[k] is not None
            else _rewrite(v, ids, base)
            for k, v in body.items()
        }
    if isinstance(body, list):
        return [_rewrite(v, ids, base) for v in body]
    if isinstance(body, str):
        # Instants reach a response inside a message as well as in a field: the
        # refusal for an identifier that disagrees with its instant quotes both.
        return _INSTANT.sub(lambda m: f"<t+{int(m.group(0)) - base}>", _ulids(body, ids))
    if isinstance(body, int) and not isinstance(body, bool) and body >= _INSTANT_FLOOR:
        return f"<t+{body - base}>"
    return body


def normalize_json(text: str) -> str:
    """Replace what a second run of the same seed would mint differently.

    Walks the parsed body rather than the text, so an instant becomes a marker
    without becoming invalid JSON, and key order — which is response-model field
    order, and part of what a refactor could change — survives into the digest.
    """
    body = json.loads(text)
    found: set[int] = set()
    _instants(body, found)
    base = min(found) if found else 0
    return json.dumps(_rewrite(body, {}, base), indent=2)


def normalize_text(text: str) -> str:
    """The same, for a response that is not JSON — an artifact's own bytes."""
    ids: dict[str, str] = {}
    text = _ulids(text, ids)
    instants = sorted({int(n) for n in _INSTANT.findall(text)})
    if instants:
        base = instants[0]
        # Descending, so no replacement can be a prefix of a longer number
        # still to be replaced.
        for n in sorted(instants, reverse=True):
            text = text.replace(str(n), f"<t+{n - base}>")
    return text


def key_paths(body: Any, prefix: str = "") -> list[str]:
    """Every path a value sits at, with list indices collapsed to `[]`.

    A readable inventory beside the digest: when a field is renamed the digest
    says only that something moved, and this says which.
    """
    if isinstance(body, dict):
        out: list[str] = []
        for k, v in body.items():
            out.extend(key_paths(v, f"{prefix}.{k}" if prefix else k))
        return out
    if isinstance(body, list):
        out = []
        for item in body:
            for p in key_paths(item, f"{prefix}[]"):
                if p not in out:
                    out.append(p)
        return out
    return [prefix]


def record(response) -> dict[str, Any]:
    is_json = response.headers.get("content-type", "").startswith("application/json")
    normalized = (normalize_json if is_json else normalize_text)(response.text)
    entry: dict[str, Any] = {
        "status": response.status_code,
        "content_type": response.headers.get("content-type"),
        "bytes": len(response.content),
        "sha256": hashlib.sha256(normalized.encode()).hexdigest(),
    }
    if is_json:
        entry["key_paths"] = sorted(set(key_paths(json.loads(normalized))))
    # Small enough to read in a diff. The timeline is a quarter of a megabyte
    # and its digest plus its key paths locate a change well enough; pasting it
    # in would make the record unreviewable, which is a worse failure than not
    # having it.
    if len(normalized) <= 2048:
        entry["body"] = normalized
    return entry


def capture(client: TestClient, world: dict[str, Any]) -> dict[str, dict]:
    """Every route, and every refusal each one has.

    Ordered, because three of these depend on what the one before it did: a
    replay is only a replay after a first delivery, and a conflicting answer is
    only a conflict after an answer.
    """
    from secondshift.db.connection import now_ms
    from secondshift.db.ids import new_ulid

    when = now_ms()
    entry = {
        "id": new_ulid(when),
        "created_at_ms": when,
        "captured_tz": "America/Los_Angeles",
        "tz_offset_min": -420,
        "policy": "cloud-assisted",
        "text": "a tool that notices when I repeat a mistake",
    }
    answer = {"answer": "the second one", "status": "decided", "modality": "text"}

    out: dict[str, dict] = {}

    def do(name: str, method: str, path: str, **kw) -> None:
        out[name] = record(client.request(method, path, **kw))

    do("health", "GET", "/health")
    do("capabilities", "GET", "/capabilities")

    do("capture_new", "POST", "/entries", json=entry)
    do("capture_replay", "POST", "/entries", json=entry)
    do("capture_divergent_replay", "POST", "/entries", json={**entry, "text": "changed"})
    do("capture_unknown_policy", "POST", "/entries",
       json={**entry, "id": new_ulid(when), "policy": "telepathy"})
    do("capture_id_disagrees_with_instant", "POST", "/entries",
       json={**entry, "id": new_ulid(when - 60_000)})

    do("runs", "GET", "/runs")
    do("timeline", "GET", f"/runs/{world['run_id']}/timeline")
    do("timeline_unknown_run", "GET", "/runs/not-a-run/timeline")

    do("event", "GET", f"/events/{world['event_id']}")
    do("event_without_model_calls", "GET", "/events/1")
    do("event_unknown", "GET", "/events/999999")

    do("artifact", "GET", f"/artifacts/{world['artifact_id']}")
    do("artifact_unknown", "GET", "/artifacts/not-an-artifact")
    do("artifact_without_a_file", "GET", f"/artifacts/{world['fileless_artifact_id']}")

    do("morning", "GET", "/morning")
    out["morning_including_nights"] = record(world["synthetic_client"].get("/morning"))
    do("answer", "POST", f"/decisions/{world['decision_id']}/answer", json=answer)
    do("answer_replay", "POST", f"/decisions/{world['decision_id']}/answer", json=answer)
    do("answer_conflict", "POST", f"/decisions/{world['decision_id']}/answer",
       json={**answer, "answer": "the first one"})
    do("answer_unknown_decision", "POST", "/decisions/not-a-decision/answer", json=answer)
    do("morning_after_answering", "GET", "/morning")

    return out


def build_world(tmp: Path) -> tuple[TestClient, dict[str, Any]]:
    """A generated night, a client over it, and the ids the capture needs.

    The one place the world is built, so the record and the test that checks it
    cannot drift into describing two different nights. It takes a directory
    rather than pytest fixtures for the same reason: the regeneration script has
    no fixtures, and a capture produced under conditions the test does not
    reproduce is a capture of nothing.
    """
    import os

    from secondshift import config
    from secondshift.airlock.capability import build_report
    from secondshift.api.app import Context, create_app
    from secondshift.config import resolve_profile
    from secondshift.db.connection import connect
    from secondshift.db.migrate import migrate
    from secondshift.db.repository import Repository
    from secondshift.telemetry.recorder import Recorder

    os.environ[config.ENV_ARTIFACTS] = str(tmp / "artifacts")

    seed_package = Path(__file__).resolve().parents[3] / "packages" / "seed"
    if str(seed_package) not in sys.path:
        sys.path.insert(0, str(seed_package))
    from secondshift_seed import generate_night

    conn = connect(tmp / "second-shift.db")
    migrate(conn)
    repo = Repository(conn)
    night = generate_night(repo, seed=SEED)

    # A row naming a file that is not there, which is a distinct refusal from an
    # unknown id and has its own message. The generator writes real bytes for
    # everything it records, so this case has to be made rather than found.
    fileless = repo.insert_artifact(
        run_id=night.run_id,
        entry_id=repo.get_run(night.run_id)["entry_id"],
        stage="build",
        kind="build",
        path="2026-08-27/nowhere/absent.md",
        is_synthetic=True,
    )

    decisions = [r["id"] for r in conn.execute("SELECT id FROM decisions ORDER BY id")]
    artifacts = [
        r["id"]
        for r in conn.execute("SELECT id FROM artifacts WHERE id != ? ORDER BY id", (fileless,))
    ]
    # The lowest event whose invocation actually made a model call. Taking the
    # first event instead leaves `model_calls` empty, and a record of an empty
    # list is a record of nothing for all ten of that model's fields — which is
    # what the first draft of this did.
    with_calls = conn.execute(
        """
        SELECT MIN(e.id) AS id FROM events e
        JOIN model_calls m ON m.agent_invocation_id = e.agent_invocation_id
        """
    ).fetchone()["id"]

    resolved = resolve_profile(env={"SECOND_SHIFT_PROFILE": "cloud"})

    def app_for(is_synthetic: bool) -> TestClient:
        return TestClient(
            create_app(
                Context(
                    repo=repo,
                    recorder=Recorder(repo, pricing=PRICING, compute_profile="cloud"),
                    profile=resolved,
                    report=build_report(resolved),
                    is_synthetic=is_synthetic,
                )
            )
        )

    world = {
        "run_id": night.run_id,
        "artifact_id": artifacts[0],
        "fileless_artifact_id": fileless,
        "decision_id": decisions[0],
        "event_id": str(with_calls),
        # A briefing assembled by a deployment that owns this night, so the
        # night lines and their artifact references are in the record. The
        # default client is not synthetic and the night is, so its briefing
        # carries questions and no nights.
        "synthetic_client": app_for(True),
    }
    return app_for(False), world


def write_golden() -> int:
    """Regenerate the record. Deliberate, and never run by the test suite."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        client, world = build_world(Path(tmp))
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(
            json.dumps(capture(client, world), indent=2, sort_keys=True) + "\n"
        )
    print(f"wrote {GOLDEN}")
    return 0


if __name__ == "__main__":
    raise SystemExit(write_golden())
