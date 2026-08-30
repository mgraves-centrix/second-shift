"""Data access.

Append-only by construction. The public surface is insertion plus a closed set
of named completion operations — `close_invocation`, `answer_decision`,
`resolve_failure`. There is deliberately no generic `update` or `delete`: the
append-only discipline in the constitution is enforced by the absence of a
method, not by remembering not to call one.

Anything that behaves like a counter is a view. `failure_ledger` derives
recurrence by grouping on signature rather than incrementing a column.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from .connection import now_ms
from .ids import new_ulid, timestamp_ms

# Tables whose rows are never modified after insertion. Completion columns on
# other tables are written through the named operations below.
APPEND_ONLY_TABLES = frozenset(
    {
        "model_calls",
        "tool_calls",
        "events",
        "artifacts",
        "outcomes",
        "model_call_payloads",
        "eval_results",
    }
)


class Repository:
    """Typed accessors over one SQLite connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    # -- internals ---------------------------------------------------------

    def _insert(self, table: str, values: dict[str, Any]) -> None:
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        self._conn.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
            tuple(values.values()),
        )

    @staticmethod
    def _id(given: str | None, ts: int) -> str:
        return given or new_ulid(ts)

    # -- capture -----------------------------------------------------------

    def insert_entry(
        self,
        *,
        created_at_ms: int,
        captured_tz: str,
        tz_offset_min: int,
        modality: str,
        default_policy: str,
        status: str,
        capture_profile: str,
        raw_text: str | None = None,
        transcript_path: str | None = None,
        audio_path: str | None = None,
        asr_provider: str | None = None,
        asr_confidence: float | None = None,
        title: str | None = None,
        source_device: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        offered_capability_json: str | None = None,
        received_at_ms: int | None = None,
        entry_id: str | None = None,
        is_synthetic: bool = False,
    ) -> str:
        """Insert a captured entry.

        `created_at_ms` is the CLIENT's capture instant and is required — it is
        never the insert time. For a queue drained hours later those differ by
        hours, which is exactly the case the offline requirement exists to
        serve. `received_at_ms` records when the server saw it; the two are kept
        independent and neither corrects the other.

        NOT LOCKED. Request handlers must use `Recorder.record_entry`, which
        takes the writer lock. See ADR 0008.
        """
        ts = created_at_ms
        eid = entry_id or new_ulid(ts)
        if entry_id is not None:
            self._assert_identifier_agrees(entry_id, ts)
        self._insert(
            "entries",
            {
                "id": eid,
                "created_at_ms": ts,
                "captured_tz": captured_tz,
                "tz_offset_min": tz_offset_min,
                "lat": lat,
                "lon": lon,
                "modality": modality,
                "raw_text": raw_text,
                "transcript_path": transcript_path,
                "audio_path": audio_path,
                "asr_provider": asr_provider,
                "asr_confidence": asr_confidence,
                "default_policy": default_policy,
                "status": status,
                "title": title,
                "source_device": source_device,
                "capture_profile": capture_profile,
                "offered_capability_json": offered_capability_json,
                "received_at_ms": received_at_ms,
                "is_synthetic": int(is_synthetic),
            },
        )
        return eid

    @staticmethod
    def _assert_identifier_agrees(entry_id: str, created_at_ms: int) -> None:
        """A client-supplied identifier must be a ULID carrying its own instant.

        Ordering uses `ORDER BY created_at_ms, id`. If the identifier's embedded
        timestamp disagrees with the recorded instant, that ordering sorts by two
        different clocks and is not a total order over anything meaningful.
        """
        try:
            embedded = timestamp_ms(entry_id)
        except ValueError as exc:
            raise ValueError(
                f"entry id {entry_id!r} is not a ULID; client-supplied "
                "identifiers must be well-formed"
            ) from exc
        if embedded != created_at_ms:
            raise ValueError(
                f"entry id {entry_id!r} carries instant {embedded} but "
                f"created_at_ms is {created_at_ms}; they must agree"
            )

    # -- the night ---------------------------------------------------------

    def insert_run(
        self,
        *,
        entry_id: str,
        night_of: str,
        effective_policy: str,
        policy_source: str,
        compute_profile: str,
        started_at_ms: int | None = None,
        brain_sha: str | None = None,
        code_sha: str | None = None,
        run_id: str | None = None,
        is_synthetic: bool = False,
    ) -> str:
        ts = started_at_ms if started_at_ms is not None else now_ms()
        rid = self._id(run_id, ts)
        self._insert(
            "runs",
            {
                "id": rid,
                "entry_id": entry_id,
                "night_of": night_of,
                "started_at_ms": ts,
                "effective_policy": effective_policy,
                "policy_source": policy_source,
                "compute_profile": compute_profile,
                "brain_sha": brain_sha,
                "code_sha": code_sha,
                "is_synthetic": int(is_synthetic),
            },
        )
        return rid

    def insert_run_stage(
        self,
        *,
        run_id: str,
        stage: str,
        seq: int,
        status: str,
        started_at_ms: int | None = None,
        stage_id: str | None = None,
    ) -> str:
        ts = now_ms()
        sid = self._id(stage_id, ts)
        self._insert(
            "run_stages",
            {
                "id": sid,
                "run_id": run_id,
                "stage": stage,
                "seq": seq,
                "status": status,
                "started_at_ms": started_at_ms,
            },
        )
        return sid

    # -- agents and telemetry ---------------------------------------------

    def insert_agent(
        self,
        *,
        name: str,
        role: str,
        version: int,
        prompt_path: str,
        prompt_sha: str,
        default_model_local: str | None = None,
        default_model_cloud: str | None = None,
        agent_id: str | None = None,
    ) -> str:
        ts = now_ms()
        aid = self._id(agent_id, ts)
        self._insert(
            "agents",
            {
                "id": aid,
                "name": name,
                "role": role,
                "version": version,
                "prompt_path": prompt_path,
                "prompt_sha": prompt_sha,
                "default_model_local": default_model_local,
                "default_model_cloud": default_model_cloud,
                "created_at_ms": ts,
            },
        )
        return aid

    def insert_agent_invocation(
        self,
        *,
        agent_id: str,
        run_id: str | None = None,
        parent_invocation_id: str | None = None,
        depth: int = 0,
        stage: str | None = None,
        input_summary: str | None = None,
        started_at_ms: int | None = None,
        invocation_id: str | None = None,
        is_synthetic: bool = False,
    ) -> str:
        ts = started_at_ms if started_at_ms is not None else now_ms()
        iid = self._id(invocation_id, ts)
        self._insert(
            "agent_invocations",
            {
                "id": iid,
                "run_id": run_id,
                "agent_id": agent_id,
                "parent_invocation_id": parent_invocation_id,
                "depth": depth,
                "stage": stage,
                "started_at_ms": ts,
                "input_summary": input_summary,
                "is_synthetic": int(is_synthetic),
            },
        )
        return iid

    def insert_model_call(
        self,
        *,
        provider: str,
        compute_profile: str,
        model: str,
        policy: str,
        estimated_cost_usd: float,
        agent_invocation_id: str | None = None,
        run_id: str | None = None,
        model_version: str | None = None,
        effort: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        reasoning_tokens: int = 0,
        total_tokens: int = 0,
        latency_ms: int | None = None,
        time_to_first_token_ms: int | None = None,
        cache_hit: bool = False,
        redaction_applied: bool = False,
        ts_ms: int | None = None,
        call_id: str | None = None,
        is_synthetic: bool = False,
    ) -> str:
        ts = ts_ms if ts_ms is not None else now_ms()
        cid = self._id(call_id, ts)
        self._insert(
            "model_calls",
            {
                "id": cid,
                "agent_invocation_id": agent_invocation_id,
                "run_id": run_id,
                "ts_ms": ts,
                "provider": provider,
                "compute_profile": compute_profile,
                "model": model,
                "model_version": model_version,
                "effort": effort,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "reasoning_tokens": reasoning_tokens,
                "total_tokens": total_tokens,
                "latency_ms": latency_ms,
                "time_to_first_token_ms": time_to_first_token_ms,
                "estimated_cost_usd": estimated_cost_usd,
                "cache_hit": int(cache_hit),
                "policy": policy,
                "redaction_applied": int(redaction_applied),
                "is_synthetic": int(is_synthetic),
            },
        )
        return cid

    def insert_tool_call(
        self,
        *,
        tool: str,
        endpoint: str,
        policy: str,
        agent_invocation_id: str | None = None,
        run_id: str | None = None,
        query_redacted: str | None = None,
        credits: float = 0.0,
        result_count: int | None = None,
        latency_ms: int | None = None,
        cached: bool = False,
        outcome: str | None = None,
        ts_ms: int | None = None,
        call_id: str | None = None,
        is_synthetic: bool = False,
    ) -> str:
        ts = ts_ms if ts_ms is not None else now_ms()
        cid = self._id(call_id, ts)
        self._insert(
            "tool_calls",
            {
                "id": cid,
                "agent_invocation_id": agent_invocation_id,
                "run_id": run_id,
                "ts_ms": ts,
                "tool": tool,
                "endpoint": endpoint,
                "query_redacted": query_redacted,
                "policy": policy,
                "credits": credits,
                "result_count": result_count,
                "latency_ms": latency_ms,
                "cached": int(cached),
                "outcome": outcome,
                "is_synthetic": int(is_synthetic),
            },
        )
        return cid

    def insert_event(
        self,
        *,
        lane: str,
        kind: str,
        label: str,
        run_id: str | None = None,
        agent_invocation_id: str | None = None,
        entry_id: str | None = None,
        model_call_id: str | None = None,
        severity: str = "info",
        duration_ms: int | None = None,
        payload_json: str | None = None,
        ts_ms: int | None = None,
        is_synthetic: bool = False,
    ) -> int:
        ts = ts_ms if ts_ms is not None else now_ms()
        cursor = self._conn.execute(
            "INSERT INTO events (run_id, agent_invocation_id, entry_id, model_call_id, "
            "ts_ms, lane, kind, label, severity, duration_ms, payload_json, is_synthetic) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                agent_invocation_id,
                entry_id,
                model_call_id,
                ts,
                lane,
                kind,
                label,
                severity,
                duration_ms,
                payload_json,
                int(is_synthetic),
            ),
        )
        return int(cursor.lastrowid)

    def insert_failure(
        self,
        *,
        failure_type: str,
        signature: str,
        message: str,
        run_id: str | None = None,
        agent_invocation_id: str | None = None,
        context_json: str | None = None,
        ts_ms: int | None = None,
        failure_id: str | None = None,
        is_synthetic: bool = False,
    ) -> str:
        ts = ts_ms if ts_ms is not None else now_ms()
        fid = self._id(failure_id, ts)
        self._insert(
            "failures",
            {
                "id": fid,
                "run_id": run_id,
                "agent_invocation_id": agent_invocation_id,
                "ts_ms": ts,
                "type": failure_type,
                "signature": signature,
                "message": message,
                "context_json": context_json,
                "is_synthetic": int(is_synthetic),
            },
        )
        return fid

    def insert_model_call_payload(
        self,
        *,
        model_call_id: str,
        prompt_path: str,
        completion_path: str,
        prompt_bytes: int | None = None,
        completion_bytes: int | None = None,
        redacted: bool = False,
        training_eligible: bool = True,
        retention_class: str = "standard",
    ) -> None:
        self._insert(
            "model_call_payloads",
            {
                "model_call_id": model_call_id,
                "prompt_path": prompt_path,
                "completion_path": completion_path,
                "prompt_bytes": prompt_bytes,
                "completion_bytes": completion_bytes,
                "captured_at_ms": now_ms(),
                "redacted": int(redacted),
                "training_eligible": int(training_eligible),
                "retention_class": retention_class,
            },
        )

    def insert_artifact(
        self,
        *,
        run_id: str,
        entry_id: str,
        stage: str,
        kind: str,
        path: str,
        variant_group: str | None = None,
        variant_index: int | None = None,
        variant_rank: int | None = None,
        content_sha: str | None = None,
        artifact_bytes: int | None = None,
        produced_by_invocation_id: str | None = None,
        created_at_ms: int | None = None,
        artifact_id: str | None = None,
        is_synthetic: bool = False,
    ) -> str:
        """Record a produced artifact.

        `variant_group` ties parallel builds of one thing together and
        `variant_rank` carries the critic's ordering within it — the two columns
        that make a fan-out legible as a comparison rather than as five unrelated
        files.
        """
        ts = created_at_ms if created_at_ms is not None else now_ms()
        aid = self._id(artifact_id, ts)
        self._insert(
            "artifacts",
            {
                "id": aid,
                "run_id": run_id,
                "entry_id": entry_id,
                "stage": stage,
                "kind": kind,
                "variant_group": variant_group,
                "variant_index": variant_index,
                "variant_rank": variant_rank,
                "path": path,
                "content_sha": content_sha,
                "bytes": artifact_bytes,
                "created_at_ms": ts,
                "produced_by_invocation_id": produced_by_invocation_id,
                "is_synthetic": int(is_synthetic),
            },
        )
        return aid

    # -- interview ---------------------------------------------------------

    def insert_decision(
        self,
        *,
        entry_id: str,
        question: str,
        status: str,
        raised_by_run_id: str | None = None,
        raised_by_invocation_id: str | None = None,
        rationale: str | None = None,
        blocking_stage: str | None = None,
        raised_at_ms: int | None = None,
        decision_id: str | None = None,
        is_synthetic: bool = False,
    ) -> str:
        ts = raised_at_ms if raised_at_ms is not None else now_ms()
        did = self._id(decision_id, ts)
        self._insert(
            "decisions",
            {
                "id": did,
                "entry_id": entry_id,
                "raised_by_run_id": raised_by_run_id,
                "raised_by_invocation_id": raised_by_invocation_id,
                "raised_at_ms": ts,
                "question": question,
                "rationale": rationale,
                "blocking_stage": blocking_stage,
                "status": status,
                "is_synthetic": int(is_synthetic),
            },
        )
        return did

    # -- named completion operations --------------------------------------
    #
    # The only writes to already-inserted rows. Each fills columns that were
    # null by construction; none overwrites a recorded value.

    def close_invocation(
        self,
        invocation_id: str,
        *,
        outcome: str,
        ended_at_ms: int | None = None,
        retry_count: int | None = None,
    ) -> None:
        """Close an open invocation. Refuses to close one that is already closed."""
        ts = ended_at_ms if ended_at_ms is not None else now_ms()
        cursor = self._conn.execute(
            "UPDATE agent_invocations SET ended_at_ms = ?, outcome = ?, "
            "retry_count = COALESCE(?, retry_count) "
            "WHERE id = ? AND ended_at_ms IS NULL",
            (ts, outcome, retry_count, invocation_id),
        )
        if cursor.rowcount != 1:
            raise ValueError(
                f"invocation {invocation_id!r} is unknown or already closed"
            )

    def close_run(
        self,
        run_id: str,
        *,
        outcome: str,
        furthest_stage: str | None = None,
        ended_at_ms: int | None = None,
    ) -> None:
        """Close an open run. Refuses to close one that is already closed.

        Without this nothing ever set `ended_at_ms`, so every run looked like it
        was still in flight — including finished ones, which makes "how long did
        last night take" unanswerable from the data.
        """
        ts = ended_at_ms if ended_at_ms is not None else now_ms()
        cursor = self._conn.execute(
            "UPDATE runs SET ended_at_ms = ?, outcome = ?, "
            "furthest_stage = COALESCE(?, furthest_stage) "
            "WHERE id = ? AND ended_at_ms IS NULL",
            (ts, outcome, furthest_stage, run_id),
        )
        if cursor.rowcount != 1:
            raise ValueError(f"run {run_id!r} is unknown or already closed")

    def complete_run_stage(
        self,
        stage_id: str,
        *,
        status: str,
        ended_at_ms: int | None = None,
        committed_at_ms: int | None = None,
        commit_sha: str | None = None,
    ) -> None:
        """Close out a stage, recording when its output was committed.

        "No empty mornings" is a query over stages that reached `complete`, and
        a stage with no end time cannot answer it.
        """
        ts = ended_at_ms if ended_at_ms is not None else now_ms()
        cursor = self._conn.execute(
            "UPDATE run_stages SET status = ?, ended_at_ms = ?, "
            "committed_at_ms = COALESCE(?, committed_at_ms), "
            "commit_sha = COALESCE(?, commit_sha) "
            "WHERE id = ? AND ended_at_ms IS NULL",
            (status, ts, committed_at_ms, commit_sha, stage_id),
        )
        if cursor.rowcount != 1:
            raise ValueError(f"run stage {stage_id!r} is unknown or already closed")

    def answer_decision(
        self,
        decision_id: str,
        *,
        answer: str,
        status: str,
        answer_modality: str = "text",
        answered_at_ms: int | None = None,
    ) -> None:
        """Record an answer against an open decision."""
        ts = answered_at_ms if answered_at_ms is not None else now_ms()
        cursor = self._conn.execute(
            "UPDATE decisions SET answer = ?, answered_at_ms = ?, "
            "answer_modality = ?, status = ? WHERE id = ? AND answered_at_ms IS NULL",
            (answer, ts, answer_modality, status, decision_id),
        )
        if cursor.rowcount != 1:
            raise ValueError(f"decision {decision_id!r} is unknown or already answered")

    #: Transitions an entry may make. Anything else is refused.
    _ENTRY_TRANSITIONS = {
        ("captured", "queued"),
        ("queued", "running"),
        ("running", "answered"),
        ("running", "queued"),
        ("answered", "archived"),
        ("queued", "archived"),
    }

    def transition_entry(self, entry_id: str, *, to_status: str) -> None:
        """Move an entry to a new status, refusing transitions that are not permitted.

        Named rather than generic: the persistence spec forbids an
        `update_entry(**fields)`, and a status machine with no guard is how an
        entry ends up somewhere nothing queries.
        """
        row = self.get_entry(entry_id)
        if row is None:
            raise ValueError(f"entry {entry_id!r} is unknown")
        current = row["status"]
        if (current, to_status) not in self._ENTRY_TRANSITIONS:
            raise ValueError(
                f"entry {entry_id!r} cannot move {current!r} -> {to_status!r}"
            )
        self._conn.execute(
            "UPDATE entries SET status = ? WHERE id = ? AND status = ?",
            (to_status, entry_id, current),
        )

    def resolve_failure(
        self, failure_id: str, *, resolution: str, resolved_at_ms: int | None = None
    ) -> None:
        """Record how a failure was resolved."""
        ts = resolved_at_ms if resolved_at_ms is not None else now_ms()
        cursor = self._conn.execute(
            "UPDATE failures SET resolution = ?, resolved_at_ms = ? "
            "WHERE id = ? AND resolved_at_ms IS NULL",
            (resolution, ts, failure_id),
        )
        if cursor.rowcount != 1:
            raise ValueError(f"failure {failure_id!r} is unknown or already resolved")

    # -- reads -------------------------------------------------------------

    def get_invocation(self, invocation_id: str) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM agent_invocations WHERE id = ?", (invocation_id,)
        ).fetchone()

    def invocation_tree(self, run_id: str) -> list[sqlite3.Row]:
        """Every invocation for a run, ordered so parents precede children.

        Joined to the agent roster for `role`, which is the column that decides
        an invocation's lane. `agent_invocations` does not carry it — role lives
        on `agents` — so selecting the table alone cannot answer the one question
        a timeline needs to ask of it.
        """
        return self._conn.execute(
            "SELECT i.*, a.role AS role, a.name AS agent_name, a.version AS agent_version "
            "FROM agent_invocations i JOIN agents a ON a.id = i.agent_id "
            "WHERE i.run_id = ? ORDER BY i.depth, i.started_at_ms, i.id",
            (run_id,),
        ).fetchall()

    def lane_roster(self, run_id: str) -> list[str]:
        """Every lane the run uses, from the run as a whole.

        Derived from the whole run rather than from a loaded window: two agent
        roles take a single invocation each across an entire night, so a roster
        built from whatever is on screen gains and loses lanes while scrubbing
        and reflows everything below them.
        """
        return [
            r["lane"]
            for r in self._conn.execute(
                "SELECT DISTINCT lane FROM events WHERE run_id = ? ORDER BY lane",
                (run_id,),
            )
        ]

    def run_detail(self, run_id: str) -> sqlite3.Row | None:
        """A run with the framing its timeline needs.

        Joins the entry for the capture offset and location. `runs` carries only
        `night_of`, a bare local date, so the axis cannot be labeled from the run
        alone — and the offset must be the one stored at capture rather than one
        resolved from the zone name later, which is wrong for half the year.
        """
        return self._conn.execute(
            "SELECT r.*, e.captured_tz AS captured_tz, e.tz_offset_min AS tz_offset_min, "
            "e.lat AS lat, e.lon AS lon, e.title AS entry_title, "
            "e.created_at_ms AS entry_created_at_ms "
            "FROM runs r JOIN entries e ON e.id = r.entry_id WHERE r.id = ?",
            (run_id,),
        ).fetchone()

    def runs_for_night(self, night_of: str) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM runs WHERE night_of = ? ORDER BY started_at_ms, id",
            (night_of,),
        ).fetchall()

    def recent_runs(self, limit: int = 50) -> list[sqlite3.Row]:
        """The most recent runs, newest first.

        Distinct from `runs_for_night`, which answers about a date someone
        already knows. This answers the question the night view opens with —
        what happened last — because being asked to name a date before seeing
        anything is friction on the one screen meant to be glanced at.
        """
        return self._conn.execute(
            "SELECT * FROM runs ORDER BY started_at_ms DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def timeline_extent(self, run_id: str) -> tuple[int, int] | None:
        """The span the axis must cover.

        The end includes each bar's duration. Work near the end of a night runs
        past the last recorded instant — by over an hour in a generated night —
        and an axis computed from timestamps alone clips it.
        """
        row = self._conn.execute(
            "SELECT MIN(ts_ms) AS lo, MAX(ts_ms + COALESCE(duration_ms, 0)) AS hi "
            "FROM events WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        return None if row["lo"] is None else (row["lo"], row["hi"])

    def captures_before_run(self, run_id: str) -> list[sqlite3.Row]:
        """The evening's captures, for the gutter beside the axis.

        Capture events carry no run, so they are invisible to a run's timeline.
        They are shown beside it rather than within it: the ideas that caused the
        night belong on screen, but the hours in which nothing ran do not belong
        in the scrubable span.
        """
        return self._conn.execute(
            "SELECT e.* FROM entries e JOIN runs r ON r.entry_id = e.id "
            "WHERE r.id = ? AND e.created_at_ms <= r.started_at_ms "
            "UNION "
            "SELECT e2.* FROM entries e2 WHERE e2.created_at_ms <= "
            "(SELECT started_at_ms FROM runs WHERE id = ?) "
            "AND e2.created_at_ms >= (SELECT started_at_ms - 86400000 FROM runs WHERE id = ?) "
            "ORDER BY created_at_ms",
            (run_id, run_id, run_id),
        ).fetchall()

    def run_stages(self, run_id: str) -> list[sqlite3.Row]:
        """Stage bands, including one still running."""
        return self._conn.execute(
            "SELECT * FROM run_stages WHERE run_id = ? ORDER BY seq",
            (run_id,),
        ).fetchall()

    def timeline_buckets(self, run_id: str, *, bucket_ms: int) -> list[sqlite3.Row]:
        """Aggregated events for a zoomed-out view.

        A bucket keeps the strongest severity present, never an average or the
        most common: one error among forty routine rows must survive being
        zoomed out, or the view hides exactly what someone is looking for.
        """
        return self._conn.execute(
            "SELECT lane, (ts_ms / ?) * ? AS bucket_start_ms, COUNT(*) AS count, "
            "MAX(CASE severity WHEN 'error' THEN 3 WHEN 'warn' THEN 2 "
            "WHEN 'info' THEN 1 ELSE 0 END) AS severity_rank "
            "FROM events WHERE run_id = ? GROUP BY lane, bucket_start_ms "
            "ORDER BY bucket_start_ms, lane",
            (bucket_ms, bucket_ms, run_id),
        ).fetchall()

    def run_spend(self, run_id: str) -> sqlite3.Row:
        """What a run cost, summed from recorded calls.

        Not from `run_cost`: every rollup view filters synthetic rows, so a
        wholly synthetic deployment — which is what the judge instance is —
        renders blank from them, on the exact instance that exists to be looked
        at.
        """
        return self._conn.execute(
            "SELECT COALESCE(SUM(estimated_cost_usd), 0) AS spend_usd, "
            "COALESCE(SUM(total_tokens), 0) AS total_tokens, COUNT(*) AS calls, "
            "COALESCE(SUM(CASE WHEN provider IN ('token-factory','nebius-job') "
            "THEN total_tokens END), 0) AS cloud_tokens, "
            "MAX(is_synthetic) AS any_synthetic "
            "FROM model_calls WHERE run_id = ?",
            (run_id,),
        ).fetchone()

    def model_calls_for_run(self, run_id: str) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM model_calls WHERE run_id = ? ORDER BY ts_ms, id", (run_id,)
        ).fetchall()

    #: An entry is eligible for a run only when it is queued, is real, and has
    #: something to reason about. Synthetic rows must never be *acted on*, not
    #: merely never counted — the day-6 night generator writes queued synthetic
    #: entries, and without this the real orchestrator would dispatch them.
    _ELIGIBLE = (
        "status = 'queued' AND is_synthetic = 0 "
        "AND COALESCE(TRIM(raw_text), '') != ''"
    )

    def dispatch_eligible_entries(self) -> list[sqlite3.Row]:
        """Entries the night may act on. Screened against capability after this."""
        return self._conn.execute(
            f"SELECT * FROM entries WHERE {self._ELIGIBLE} ORDER BY created_at_ms, id"
        ).fetchall()

    def ineligible_entries(self) -> list[tuple[sqlite3.Row, str]]:
        """Queued entries that cannot be dispatched, each with its reason.

        An entry that can never run must not be silently invisible; that is how
        an idea disappears without anyone noticing it never happened.
        """
        rows = self._conn.execute(
            f"SELECT * FROM entries WHERE status = 'queued' AND NOT ({self._ELIGIBLE}) "
            "ORDER BY created_at_ms, id"
        ).fetchall()
        out: list[tuple[sqlite3.Row, str]] = []
        for row in rows:
            if row["is_synthetic"]:
                reason = "synthetic entries are never dispatched"
            else:
                reason = "entry has no content to reason about"
            out.append((row, reason))
        return out

    def get_entry(self, entry_id: str) -> sqlite3.Row | None:
        """Fetch one entry. The idempotent replay path returns what is stored."""
        return self._conn.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        ).fetchone()

    def entry_history(self, entry_id: str) -> list[sqlite3.Row]:
        """Events naming this entry, including those with no run."""
        return self._conn.execute(
            "SELECT id, ts_ms, lane, kind, label, severity, duration_ms, run_id "
            "FROM events WHERE entry_id = ? ORDER BY ts_ms, id",
            (entry_id,),
        ).fetchall()

    def model_call_for_event(self, event_id: int) -> sqlite3.Row | None:
        """The call an event names, or None where it names none.

        Exact by construction. Correlating on invocation and instant would be
        wrong for any invocation that made two calls in one millisecond, and
        wrong silently — which is worse than reporting nothing.
        """
        return self._conn.execute(
            "SELECT m.* FROM events e JOIN model_calls m ON m.id = e.model_call_id "
            "WHERE e.id = ?",
            (event_id,),
        ).fetchone()

    def failure_ledger(self) -> list[sqlite3.Row]:
        """Recurrence derived from signatures, never a stored counter."""
        return self._conn.execute(
            "SELECT * FROM failure_ledger ORDER BY recurrence_count DESC, last_seen_ms DESC"
        ).fetchall()

    def timeline(
        self,
        run_id: str,
        *,
        from_ms: int | None = None,
        to_ms: int | None = None,
        limit: int | None = None,
        after: tuple[int, int] | None = None,
    ) -> list[sqlite3.Row]:
        """Scalar columns only — the scrubber never parses JSON to draw a frame."""
        clauses = ["run_id = ?"]
        params: list[object] = [run_id]
        if from_ms is not None:
            # A bar starting before the window but running into it is inside it.
            clauses.append("ts_ms + COALESCE(duration_ms, 0) >= ?")
            params.append(from_ms)
        if to_ms is not None:
            clauses.append("ts_ms <= ?")
            params.append(to_ms)
        if after is not None:
            # Paging on (ts_ms, id), never id alone: the integer key is not
            # monotonic in time. Depth-first spawning places a child's events at
            # earlier instants than its siblings, and a real night carries
            # hundreds of such inversions.
            clauses.append("(ts_ms > ? OR (ts_ms = ? AND id > ?))")
            params.extend([after[0], after[0], after[1]])

        sql = (
            "SELECT id, ts_ms, lane, kind, label, severity, duration_ms, "
            "agent_invocation_id, model_call_id, is_synthetic FROM events "
            f"WHERE {' AND '.join(clauses)} ORDER BY ts_ms, id"
        )
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return self._conn.execute(sql, tuple(params)).fetchall()
