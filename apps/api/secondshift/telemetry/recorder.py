"""The telemetry recorder.

Owns the invocation lifecycle rather than being called alongside it: an
invocation cannot be left open by an early return or an exception, because a
context manager closes it. Model and tool calls read the current invocation
from context, so a provider never has to be handed an id it might forget to
pass on.

All writes serialize through one lock. The database has a single writer by
design, and externally-attributed telemetry from out-of-process work arrives
through the same path rather than opening a second connection.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from ..db.connection import now_ms
from ..db.repository import Repository
from . import context as ctx
from .failures import FailureType, classify, signature
from .pricing import PricingTable


class UnknownDispatcher(LookupError):
    """Externally-attributed telemetry named an invocation that does not exist."""


@dataclass(slots=True)
class ExternalInvocation:
    """An invocation that executed outside this process."""

    local_id: str
    agent_id: str
    parent_local_id: str | None = None
    stage: str | None = None
    input_summary: str | None = None
    started_at_ms: int | None = None
    ended_at_ms: int | None = None
    outcome: str = "success"


@dataclass(slots=True)
class ExternalModelCall:
    """A model call made by out-of-process work."""

    parent_local_id: str
    provider: str
    model: str
    policy: str
    compute_profile: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int | None = None
    ts_ms: int | None = None


@dataclass(slots=True)
class TelemetryDescriptor:
    """Passed to out-of-process work so its telemetry can rejoin the tree.

    Carried by `Executor.dispatch`. `JobResult` never carries telemetry, which
    keeps the executor interface independent of any serialization format.
    """

    ingest_url: str
    credential: str
    dispatching_invocation_id: str
    run_id: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


class Recorder:
    def __init__(
        self,
        repo: Repository,
        *,
        pricing: PricingTable,
        compute_profile: str,
    ) -> None:
        self._repo = repo
        self._pricing = pricing
        self._profile = compute_profile
        self._lock = threading.Lock()

    @property
    def compute_profile(self) -> str:
        return self._profile

    # -- invocations -------------------------------------------------------

    @contextmanager
    def invocation(
        self,
        agent_id: str,
        *,
        run_id: str | None = None,
        stage: str | None = None,
        input_summary: str | None = None,
        is_synthetic: bool = False,
    ) -> Iterator[str]:
        """Open an invocation, yield its id, and close it on the way out.

        Parentage and depth come from the surrounding context, so nesting is
        automatic. On an exception the invocation closes as failed and a typed
        failure row is written before the exception propagates.
        """
        parent = ctx.current()
        effective_run = run_id or (parent.run_id if parent else None)
        depth = parent.depth + 1 if parent else 0

        with self._lock:
            invocation_id = self._repo.insert_agent_invocation(
                agent_id=agent_id,
                run_id=effective_run,
                parent_invocation_id=parent.invocation_id if parent else None,
                depth=depth,
                stage=stage,
                input_summary=input_summary,
                is_synthetic=is_synthetic,
            )

        token = ctx.bind(
            ctx.InvocationContext(
                invocation_id=invocation_id, run_id=effective_run, depth=depth
            )
        )
        try:
            yield invocation_id
        except BaseException as exc:
            failure_type = classify(exc)
            with self._lock:
                self._repo.insert_failure(
                    failure_type=str(failure_type),
                    signature=signature(failure_type, exc, scope=stage or "invocation"),
                    message=str(exc) or type(exc).__name__,
                    run_id=effective_run,
                    agent_invocation_id=invocation_id,
                    is_synthetic=is_synthetic,
                )
                self._repo.close_invocation(invocation_id, outcome="failed")
            raise
        else:
            with self._lock:
                self._repo.close_invocation(invocation_id, outcome="success")
        finally:
            ctx.release(token)

    # -- capture -----------------------------------------------------------

    def record_run(self, **fields: Any) -> str:
        """Open a run under the writer lock, pinning the brain's current commit.

        Pinned at start, not at end: the memory that shaped a run is the state it
        began from. Where the brain cannot be read the commit is left unset
        rather than filled with a placeholder, which would later be
        indistinguishable from a real state.
        """
        if "brain_sha" not in fields:
            from ..brain.repo import BrainRepo

            fields["brain_sha"] = BrainRepo().head()
        with self._lock:
            return self._repo.insert_run(**fields)

    def record_entry(self, **fields: Any) -> str:
        """Insert a captured entry under the writer lock.

        `Repository.insert_entry` is the unlocked primitive. Request handlers
        must come through here: the connection has `check_same_thread` disabled
        so that threaded work can record telemetry, and FastAPI runs synchronous
        handlers in a threadpool — so a capture arriving while the night writes
        is a real interleaving, not a theoretical one. ADR 0008.
        """
        with self._lock:
            return self._repo.insert_entry(**fields)

    def transition_entry(self, entry_id: str, *, to_status: str) -> None:
        """Move an entry between statuses under the writer lock."""
        with self._lock:
            self._repo.transition_entry(entry_id, to_status=to_status)

    # -- calls -------------------------------------------------------------

    def record_model_call(
        self,
        *,
        provider: str,
        model: str,
        policy: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        reasoning_tokens: int = 0,
        latency_ms: int | None = None,
        time_to_first_token_ms: int | None = None,
        model_version: str | None = None,
        effort: str | None = None,
        cache_hit: bool = False,
        redaction_applied: bool = False,
        compute_profile: str | None = None,
        ts_ms: int | None = None,
        is_synthetic: bool = False,
    ) -> str:
        """Record a completion. Cost is computed from the rate in effect."""
        active = ctx.current()
        ts = ts_ms if ts_ms is not None else now_ms()
        cost = self._pricing.cost_usd(
            provider=provider,
            model=model,
            ts_ms=ts,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        with self._lock:
            return self._repo.insert_model_call(
                provider=provider,
                compute_profile=compute_profile or self._profile,
                model=model,
                model_version=model_version,
                policy=policy,
                effort=effort,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                reasoning_tokens=reasoning_tokens,
                total_tokens=prompt_tokens + completion_tokens + reasoning_tokens,
                latency_ms=latency_ms,
                time_to_first_token_ms=time_to_first_token_ms,
                estimated_cost_usd=cost,
                cache_hit=cache_hit,
                redaction_applied=redaction_applied,
                agent_invocation_id=active.invocation_id if active else None,
                run_id=active.run_id if active else None,
                ts_ms=ts,
                is_synthetic=is_synthetic,
            )

    def record_tool_call(
        self,
        *,
        tool: str,
        endpoint: str,
        policy: str,
        query_redacted: str | None = None,
        credits: float = 0.0,
        result_count: int | None = None,
        latency_ms: int | None = None,
        cached: bool = False,
        outcome: str | None = "success",
        is_synthetic: bool = False,
    ) -> str:
        """Record an external tool call. Only the redacted query is stored."""
        active = ctx.current()
        with self._lock:
            return self._repo.insert_tool_call(
                tool=tool,
                endpoint=endpoint,
                policy=policy,
                query_redacted=query_redacted,
                credits=credits,
                result_count=result_count,
                latency_ms=latency_ms,
                cached=cached,
                outcome=outcome,
                agent_invocation_id=active.invocation_id if active else None,
                run_id=active.run_id if active else None,
                is_synthetic=is_synthetic,
            )

    def record_event(
        self,
        *,
        lane: str,
        kind: str,
        label: str,
        entry_id: str | None = None,
        model_call_id: str | None = None,
        severity: str = "info",
        duration_ms: int | None = None,
        payload_json: str | None = None,
        ts_ms: int | None = None,
        is_synthetic: bool = False,
    ) -> int:
        """Record a timeline event with pre-rendered scalar columns."""
        active = ctx.current()
        with self._lock:
            return self._repo.insert_event(
                lane=lane,
                kind=kind,
                label=label,
                entry_id=entry_id,
                model_call_id=model_call_id,
                severity=severity,
                duration_ms=duration_ms,
                payload_json=payload_json,
                agent_invocation_id=active.invocation_id if active else None,
                run_id=active.run_id if active else None,
                ts_ms=ts_ms,
                is_synthetic=is_synthetic,
            )

    def record_failure(
        self,
        exc: BaseException,
        *,
        scope: str = "",
        context_json: str | None = None,
        is_synthetic: bool = False,
    ) -> str:
        """Classify and record a failure outside an invocation boundary."""
        active = ctx.current()
        failure_type: FailureType = classify(exc)
        with self._lock:
            return self._repo.insert_failure(
                failure_type=str(failure_type),
                signature=signature(failure_type, exc, scope=scope),
                message=str(exc) or type(exc).__name__,
                context_json=context_json,
                run_id=active.run_id if active else None,
                agent_invocation_id=active.invocation_id if active else None,
                is_synthetic=is_synthetic,
            )

    # -- out-of-process attribution ---------------------------------------

    def descriptor_for(
        self, *, ingest_url: str, credential: str
    ) -> TelemetryDescriptor:
        """Build the descriptor that dispatched work carries."""
        active = ctx.current()
        if active is None:
            raise RuntimeError(
                "cannot dispatch outside an invocation: remote telemetry would "
                "have no parent to attach to"
            )
        return TelemetryDescriptor(
            ingest_url=ingest_url,
            credential=credential,
            dispatching_invocation_id=active.invocation_id,
            run_id=active.run_id,
        )

    def ingest_external(
        self,
        dispatching_invocation_id: str,
        *,
        invocations: list[ExternalInvocation] | None = None,
        model_calls: list[ExternalModelCall] | None = None,
        is_synthetic: bool = False,
    ) -> dict[str, str]:
        """Attach telemetry from out-of-process work under its dispatcher.

        Returns the mapping from the caller's local ids to recorded ids.

        The authenticated transport that carries this from a remote job is
        delivered with the Nebius executor. This is the recorder-side contract
        that transport depends on: it validates the dispatcher exists, so an
        unknown or forged parent cannot create orphaned rows.
        """
        with self._lock:
            dispatcher = self._repo.get_invocation(dispatching_invocation_id)
            if dispatcher is None:
                raise UnknownDispatcher(
                    f"no invocation {dispatching_invocation_id!r}; refusing to "
                    "write telemetry that would be orphaned"
                )

            run_id = dispatcher["run_id"]
            base_depth = dispatcher["depth"]
            resolved: dict[str, str] = {}

            for external in invocations or []:
                if external.parent_local_id is None:
                    parent_id = dispatching_invocation_id
                    depth = base_depth + 1
                else:
                    if external.parent_local_id not in resolved:
                        raise UnknownDispatcher(
                            f"parent {external.parent_local_id!r} not yet recorded; "
                            "order invocations parents-first"
                        )
                    parent_id = resolved[external.parent_local_id]
                    parent_row = self._repo.get_invocation(parent_id)
                    depth = parent_row["depth"] + 1

                recorded = self._repo.insert_agent_invocation(
                    agent_id=external.agent_id,
                    run_id=run_id,
                    parent_invocation_id=parent_id,
                    depth=depth,
                    stage=external.stage,
                    input_summary=external.input_summary,
                    started_at_ms=external.started_at_ms,
                    is_synthetic=is_synthetic,
                )
                self._repo.close_invocation(
                    recorded,
                    outcome=external.outcome,
                    ended_at_ms=external.ended_at_ms or now_ms(),
                )
                resolved[external.local_id] = recorded

            for call in model_calls or []:
                if call.parent_local_id not in resolved:
                    raise UnknownDispatcher(
                        f"model call names unknown invocation {call.parent_local_id!r}"
                    )
                ts = call.ts_ms if call.ts_ms is not None else now_ms()
                self._repo.insert_model_call(
                    provider=call.provider,
                    compute_profile=call.compute_profile,
                    model=call.model,
                    policy=call.policy,
                    prompt_tokens=call.prompt_tokens,
                    completion_tokens=call.completion_tokens,
                    total_tokens=call.total_tokens
                    or call.prompt_tokens + call.completion_tokens,
                    latency_ms=call.latency_ms,
                    estimated_cost_usd=self._pricing.cost_usd(
                        provider=call.provider,
                        model=call.model,
                        ts_ms=ts,
                        prompt_tokens=call.prompt_tokens,
                        completion_tokens=call.completion_tokens,
                    ),
                    agent_invocation_id=resolved[call.parent_local_id],
                    run_id=run_id,
                    ts_ms=ts,
                    is_synthetic=is_synthetic,
                )

            return resolved
