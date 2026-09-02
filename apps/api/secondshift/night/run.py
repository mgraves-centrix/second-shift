"""One night: dispatch, walk the stages, close the run.

Principle 3 lives here. Each stage opens, runs and closes in its own
transaction — kill the process halfway and every stage that finished is still
`complete`, still has its end time, and still renders. There is deliberately no
transaction spanning two stages; the constitution names that as the violation.

Nothing in this module writes telemetry directly. `Recorder.invocation` opens
and closes the invocation with parentage from the surrounding context, and the
`Reasoner` base class records the model call. A pipeline that recorded its own
rows is a pipeline that can record them differently from every other caller.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from ..agents.invoke import invoke
from ..airlock.policy import resolve_policy
from ..brain.repo import BrainRepo, BrainUnavailable
from ..db.connection import now_ms
from ..db.repository import Repository
from ..providers.registry import Providers
from ..telemetry.recorder import Recorder
from .stages import STAGES, Stage

#: What a stage row records when a stage never ran. `skipped` is not `failed`:
#: nothing was attempted, so nothing broke, and a morning that reports them the
#: same way cannot tell "we could not" from "we did not have to".
SKIPPED = "skipped"
COMPLETE = "complete"
FAILED = "failed"
RUNNING = "running"

#: Where `distill` writes. Additive, one file per night, beside the journal —
#: never a rewrite of `profile.md` or `style-guide.md`.
#:
#: The distiller's own prompt says to prefer editing an existing belief to
#: appending a new one, and that is the right long-term shape. It is not done
#: here: rewriting a topic file from a model completion nobody has read against
#: the real reasoner would compound an over-confident inference silently for
#: weeks, which is the failure that prompt itself warns about. Append first,
#: read what it actually produces, then earn the rewrite.
NIGHTS_DIR = "nights"

#: Handed to the brief stage when retrieval produced nothing. Said out loud
#: because the alternative is a brief that looks memory-informed and is not.
NO_RETRIEVAL_NOTE = (
    "No retrieved context is available for this run — the local embedding index "
    "could not be built. Write the brief from the idea alone, and say in it that "
    "you had no memory of earlier work to draw on."
)


@dataclass(frozen=True, slots=True)
class StageResult:
    stage: str
    status: str
    reason: str | None = None
    text: str = ""


@dataclass(frozen=True, slots=True)
class NightResult:
    """What one entry's night did. `run_id` is None where it never opened."""

    entry_id: str
    run_id: str | None
    outcome: str | None
    stages: list[StageResult] = field(default_factory=list)
    quarantine_reason: str | None = None

    @property
    def quarantined(self) -> bool:
        return self.run_id is None


class Quarantined(RuntimeError):
    """The resolved policy is not permitted on this profile.

    Raised internally and caught by `run_entry`, which records it and returns
    rather than propagating: one entry the profile cannot serve must not stop
    the other entries in the same night.
    """


def _outcome_for(results: list[StageResult]) -> str:
    """Derive the run's outcome from what its stages actually did.

    `degraded` is the expected outcome of every night today, because `research`
    has no provider and is skipped. Reporting that as `complete` would hide a
    gap the morning is supposed to be able to name.
    """
    completed = [r for r in results if r.status == COMPLETE]
    if not completed:
        return "failed"
    if len(completed) == len(STAGES):
        return "complete"
    return "degraded"


def _context_for(stage: Stage, results: dict[str, StageResult]) -> str:
    """What this stage is handed: the completed output of what it depends on.

    Assembled here rather than retrieved: an agent takes what it is given and
    does no retrieval of its own (`agents.invoke`'s contract).
    """
    parts = [
        f"## {name} ({r.stage})\n\n{r.text}"
        for name, r in results.items()
        if r.status == COMPLETE and r.text
    ]
    return "\n\n".join(parts)


def _run_stage(
    repo: Repository,
    recorder: Recorder,
    providers: Providers,
    stage: Stage,
    *,
    run_id: str,
    agents: dict[str, str],
    prompts: dict[str, object],
    entry_text: str,
    policy: str,
    completed: frozenset[str],
    results: dict[str, StageResult],
    retrieved: str,
    brain: BrainRepo | None,
) -> StageResult:
    """One stage, in its own transaction. Never raises.

    A stage that raises is recorded `failed` with a typed failure and the walk
    continues wherever the predicates allow — the whole point of principle 3 is
    that a late failure does not retract an early success.
    """
    blocked = stage.blocked_reason(completed)
    if blocked is not None:
        # Skipped stages are recorded and closed in one go: there is no window
        # in which they were running, so opening them as `running` first would
        # be a lie the scrubber would draw.
        stage_id = repo.insert_run_stage(
            run_id=run_id, stage=stage.name, seq=stage.seq, status=RUNNING
        )
        repo.complete_run_stage(stage_id, status=SKIPPED)
        return StageResult(stage.name, SKIPPED, reason=blocked)

    stage_id = repo.insert_run_stage(
        run_id=run_id,
        stage=stage.name,
        seq=stage.seq,
        status=RUNNING,
        started_at_ms=now_ms(),
    )
    context = _context_for(stage, results)
    if stage.name == "brief":
        # An absent index is stated, never silently absorbed. A brief written
        # with no memory behind it reads exactly like one written with memory
        # that had nothing to say, and the morning cannot tell them apart.
        context = retrieved or NO_RETRIEVAL_NOTE
    try:
        turn = invoke(
            recorder,
            providers.reasoner,
            role=stage.role,
            agent_id=agents[stage.role],
            prompt_path=prompts[stage.role],  # type: ignore[arg-type]
            task=entry_text,
            policy=policy,
            run_id=run_id,
            stage=stage.name,
            context=context,
        )
    except Exception as exc:  # noqa: BLE001 - recorded, classified, not swallowed
        # Recorded before the stage closes, so the failure and the stage row
        # cannot disagree about whether this stage failed.
        recorder.record_failure(exc, scope=f"night.{stage.name}")
        repo.complete_run_stage(stage_id, status=FAILED)
        return StageResult(stage.name, FAILED, reason=str(exc) or type(exc).__name__)

    committed_at, commit_sha = (None, None)
    if stage.name == "distill" and brain is not None:
        committed_at, commit_sha = _write_to_brain(brain, run_id, turn.text)

    repo.complete_run_stage(
        stage_id,
        status=COMPLETE,
        committed_at_ms=committed_at,
        commit_sha=commit_sha,
    )
    return StageResult(stage.name, COMPLETE, text=turn.text)


def _write_to_brain(
    brain: BrainRepo, run_id: str, text: str
) -> tuple[int | None, str | None]:
    """Append this night's distillation and commit it. Never raises.

    An unavailable or unwritable brain must not fail a night that otherwise
    worked — principle 3 again. The stage still completes; `commit_sha` stays
    null, which reads as "not committed" rather than as a claim nobody can
    check.
    """
    try:
        night_dir = brain.path / NIGHTS_DIR
        night_dir.mkdir(parents=True, exist_ok=True)
        path = night_dir / f"{datetime.now(UTC).strftime('%Y-%m-%d')}-{run_id}.md"
        path.write_text(
            f"# Night {datetime.now(UTC).strftime('%Y-%m-%d')}\n\n"
            f"Run `{run_id}`.\n\n{text}\n"
        )
        sha = brain.commit_paths(
            [str(path.relative_to(brain.path))], f"night: distill {run_id}"
        )
    except (BrainUnavailable, OSError):
        return None, None
    return (now_ms(), sha) if sha else (None, None)


def run_entry(
    repo: Repository,
    recorder: Recorder,
    providers: Providers,
    entry: dict | object,
    *,
    profile: str,
    agents: dict[str, str],
    prompts: dict[str, object],
    local_available: bool,
    unavailable_reason: str | None = None,
    night_of: str | None = None,
    retrieved: str = "",
    brain_sha: str | None = None,
    brain: BrainRepo | None = None,
) -> NightResult:
    """Work one entry through the stages, and close its run on every path."""
    entry_id = entry["id"]
    entry_text = entry["raw_text"] or ""

    resolution = resolve_policy(
        entry["default_policy"],
        available=local_available,
        unavailable_reason=unavailable_reason,
    )
    if not resolution.permitted:
        # Quarantine is a refusal *before* dispatch, not a run of skipped
        # stages. `runs` is the denominator of the cost-per-artifact curve, and
        # a night that never happened must not enter it.
        #
        # The failure taxonomy has no entry for a policy refusal; this uses the
        # module's own documented fallback ("the closest applicable type") and
        # scopes the signature to `night.quarantine` so it still groups
        # distinctly in the ledger. Adding a `policy_refused` type is a
        # migration, which is a data-model change beyond this capability.
        recorder.record_failure(
            Quarantined(resolution.cause or "policy not permitted on this profile"),
            scope="night.quarantine",
        )
        return NightResult(
            entry_id=entry_id,
            run_id=None,
            outcome=None,
            quarantine_reason=resolution.cause,
        )

    repo.transition_entry(entry_id, to_status="running")
    run_id = repo.insert_run(
        entry_id=entry_id,
        night_of=night_of or datetime.now(UTC).strftime("%Y-%m-%d"),
        effective_policy=str(resolution.effective_policy),
        policy_source=str(resolution.policy_source),
        compute_profile=profile,
        brain_sha=brain_sha,
    )

    results: dict[str, StageResult] = {}
    ordered: list[StageResult] = []
    try:
        for stage in STAGES:
            completed = frozenset(n for n, r in results.items() if r.status == COMPLETE)
            result = _run_stage(
                repo,
                recorder,
                providers,
                stage,
                run_id=run_id,
                agents=agents,
                prompts=prompts,
                entry_text=entry_text,
                policy=str(resolution.effective_policy),
                completed=completed,
                results=results,
                retrieved=retrieved,
                brain=brain,
            )
            results[stage.name] = result
            ordered.append(result)
    finally:
        # Every terminal path, including the exception one. `close_run` had no
        # caller at all before this capability, which is why every recorded run
        # looked permanently in flight.
        outcome = _outcome_for(ordered)
        furthest = next(
            (r.stage for r in reversed(ordered) if r.status == COMPLETE), None
        )
        repo.close_run(run_id, outcome=outcome, furthest_stage=furthest)
        # A failed night returns the entry to `queued`: there is no failed state
        # for an entry, which is a decision the schema already took. An idea
        # that could not be worked on tonight is one to work on tomorrow.
        repo.transition_entry(
            entry_id, to_status="queued" if outcome == "failed" else "answered"
        )

    return NightResult(entry_id=entry_id, run_id=run_id, outcome=outcome, stages=ordered)
