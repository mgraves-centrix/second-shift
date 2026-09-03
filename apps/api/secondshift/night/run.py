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

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ..agents.invoke import invoke
from ..airlock.policy import resolve_policy
from ..artifacts.store import VARIANT_KINDS, ArtifactWriteFailed, write_artifact
from ..artifacts.variants import RankingRefused, parse_ordering, rank_group, write_variants
from ..brain.repo import BrainRepo, BrainUnavailable
from ..morning.interview import mark_consumed, queued_for_tonight
from .research import run_research
from ..db.connection import now_ms
from ..db.repository import Repository
from ..providers.registry import Providers
from ..telemetry.recorder import Recorder
from .stages import STAGES, Stage

#: `## Variant 1`, at the start of a line. What the builder prompt asks for.
_VARIANT_SPLIT = re.compile(r"^##\s*Variant\s+\d+.*$", re.M | re.I)

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
    #: Artifact ids this stage landed. Empty where it produced no file — a
    #: stage that ran but wrote nothing is distinguishable from one that wrote.
    artifacts: tuple[str, ...] = ()
    #: The `variant_group` this stage opened, where it produced a fan-out.
    variant_group: str | None = None


@dataclass(frozen=True, slots=True)
class NightResult:
    """What one entry's night did. `run_id` is None where it never opened."""

    entry_id: str
    run_id: str | None
    outcome: str | None
    stages: list[StageResult] = field(default_factory=list)
    quarantine_reason: str | None = None
    #: What the run actually executed under. Carried out because anything that
    #: runs *after* the stages — the interviewer, for one — has to honor the
    #: same policy, and a caller that guessed it could send a `local-only`
    #: night's facts to a remote provider.
    effective_policy: str | None = None

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
    answers: str,
    policy: str,
    completed: frozenset[str],
    results: dict[str, StageResult],
    retrieved: str,
    brain: BrainRepo | None,
    entry_id: str,
    night_of: str,
    artifact_root: Path | None,
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
    # Research is a tool call, not a model call, so it runs before the agent
    # rather than through it: the searching is the stage's work, and the
    # researcher's turn is what reads the results.
    if stage.name == "research":
        return _run_research_stage(
            repo,
            recorder,
            stage_id,
            stage,
            entry_text=entry_text,
            policy=policy,
            run_id=run_id,
            entry_id=entry_id,
            night_of=night_of,
            invocation_id=None,
            artifact_root=artifact_root,
        )

    context = _context_for(stage, results)
    if stage.name == "brief":
        # An absent index is stated, never silently absorbed. A brief written
        # with no memory behind it reads exactly like one written with memory
        # that had nothing to say, and the morning cannot tell them apart.
        context = retrieved or NO_RETRIEVAL_NOTE
    if answers:
        # Prepended, so what the person decided leads rather than trails the
        # retrieved context. An answer given this morning is the most recent
        # and most authoritative thing the system knows about this idea.
        context = f"{answers}\n\n{context}" if context else answers
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

    # The artifact lands before the stage closes. A stage recorded `complete`
    # whose file is not there would be a morning that promises something it
    # cannot open.
    try:
        landed, group = _write_output(
            repo,
            stage,
            turn.text,
            run_id=run_id,
            entry_id=entry_id,
            night_of=night_of,
            invocation_id=turn.invocation_id,
            root=artifact_root,
        )
    except ArtifactWriteFailed as exc:
        recorder.record_failure(exc, scope=f"night.{stage.name}.artifact")
        repo.complete_run_stage(stage_id, status=FAILED)
        return StageResult(stage.name, FAILED, reason=str(exc))

    repo.complete_run_stage(
        stage_id,
        status=COMPLETE,
        committed_at_ms=committed_at,
        commit_sha=commit_sha,
    )
    return StageResult(
        stage.name,
        COMPLETE,
        text=turn.text,
        artifacts=tuple(landed),
        variant_group=group,
    )


def _run_research_stage(
    repo: Repository,
    recorder: Recorder,
    stage_id: str,
    stage: Stage,
    *,
    entry_text: str,
    policy: str,
    run_id: str,
    entry_id: str,
    night_of: str,
    invocation_id: str | None,
    artifact_root: Path | None,
) -> StageResult:
    """The one stage that talks outward. Skips are reasons, not failures.

    A skip here is `skipped`, never `failed`: no credential and a `local-only`
    policy are both facts about the deployment rather than something that broke,
    and a morning that reported them as failures would be reporting a defect
    that does not exist. A quota refusal *is* a failure, and a typed one.
    """
    try:
        outcome = run_research(recorder, policy=policy, entry_text=entry_text)
    except Exception as exc:  # noqa: BLE001 - classified and recorded, not swallowed
        recorder.record_failure(exc, scope="night.research")
        repo.complete_run_stage(stage_id, status=FAILED)
        return StageResult(stage.name, FAILED, reason=str(exc) or type(exc).__name__)

    if not outcome.searched:
        repo.complete_run_stage(stage_id, status=SKIPPED)
        return StageResult(stage.name, SKIPPED, reason=outcome.reason)

    # The digest lands like any other stage's output. `produced_by_invocation_id`
    # is null here and correctly so: a search is a tool call, not an agent
    # invocation, and claiming one would point at a row that does not exist.
    try:
        landed, _ = _write_output(
            repo,
            stage,
            outcome.digest,
            run_id=run_id,
            entry_id=entry_id,
            night_of=night_of,
            invocation_id=invocation_id,
            root=artifact_root,
        )
    except ArtifactWriteFailed as exc:
        recorder.record_failure(exc, scope="night.research.artifact")
        repo.complete_run_stage(stage_id, status=FAILED)
        return StageResult(stage.name, FAILED, reason=str(exc))

    repo.complete_run_stage(stage_id, status=COMPLETE)
    return StageResult(
        stage.name, COMPLETE, text=outcome.digest, artifacts=tuple(landed)
    )


def _write_output(
    repo: Repository,
    stage: Stage,
    text: str,
    *,
    run_id: str,
    entry_id: str,
    night_of: str,
    invocation_id: str | None,
    root: Path | None,
) -> tuple[list[str], str | None]:
    """Land this stage's output. Returns the artifact ids and any group.

    Variant kinds fan out; everything else writes one file. **No rank is passed
    anywhere in here** — a rank is what a critic produced, and at write time the
    critic has not spoken. That is what makes it structurally impossible for the
    writer to default a rank to the generation index.

    The fan-out is sequential today and that is the seam `nebius-executor`
    substitutes at: it takes a list of variant bodies and does not care whether
    they were produced in a loop or by five parallel Jobs.
    """
    if stage.artifact_kind is None:
        return [], None
    if stage.artifact_kind in VARIANT_KINDS:
        produced = write_variants(
            repo,
            run_id=run_id,
            entry_id=entry_id,
            night_of=night_of,
            stage=stage.name,
            kind=stage.artifact_kind,
            contents=_variant_bodies(text),
            produced_by_invocation_id=invocation_id,
            root=root,
        )
        return [w.artifact_id for w in produced.written], produced.group
    written = write_artifact(
        repo,
        run_id=run_id,
        entry_id=entry_id,
        night_of=night_of,
        stage=stage.name,
        kind=stage.artifact_kind,
        content=text,
        produced_by_invocation_id=invocation_id,
        root=root,
    )
    return [written.artifact_id], None


def _variant_bodies(text: str) -> list[str]:
    """Split one completion into the variants it proposed.

    Splits on a top-level `## Variant N` heading. **No shipped prompt asks for
    that heading**, which was found by re-reading them after this shipped: the
    architect and builder both end with "Answer in plain prose," and neither
    mentions variants at all. An earlier version of this docstring claimed they
    did. They do not.

    The consequence, stated plainly rather than left to be discovered: **a
    fan-out produces exactly one variant today.** The machinery is correct and
    the input never exercises it. Making it real means a `v2` builder prompt
    that asks for the format — which is the subject's call, because a prompt
    change resets `prompt_sha` and with it that role's eight-week curve.

    A completion with no heading is one variant, not zero: a model that ignored
    a format still produced something worth keeping, and dropping it would lose
    real work to a formatting miss. That is why the current state degrades to
    one rather than to nothing.
    """
    parts = _VARIANT_SPLIT.split(text)
    bodies = [p.strip() for p in parts if p.strip()]
    return bodies or [text]


def _take_queued_answers(repo: Repository, run_id: str) -> str:
    """Answers waiting for tonight, marked consumed and rendered as context.

    Consuming here rather than at answer time is what makes "answering changes
    tonight" visible in the data: `consumed_by_run_id` names the run that acted
    on it, so a decision the person answered and a decision the system used are
    distinguishable.
    """
    lines: list[str] = []
    for row in queued_for_tonight(repo):
        mark_consumed(repo, row["id"], run_id)
        lines.append(f"You were asked: {row['question']}\nYou answered: {row['answer']}")
    if not lines:
        return ""
    return "What you decided this morning:\n\n" + "\n\n".join(lines)


def _rank_the_builds(
    repo: Repository,
    recorder: Recorder,
    results: dict[str, StageResult],
    critique: str,
) -> None:
    """Apply the critic's ordering to the build group. Never raises.

    A refused ranking leaves every `variant_rank` null, which is the honest
    value for "the critic did not produce a usable ordering." The alternative —
    falling back to the generation order — would fill the column with plausible
    numbers that are really the order things happened to be built in, and
    nothing downstream could tell them from a real ranking.
    """
    build = results.get("build")
    if build is None or build.variant_group is None:
        return
    try:
        rank_group(repo, build.variant_group, parse_ordering(critique))
    except RankingRefused as exc:
        # Recorded rather than swallowed: an unrankable critique is evidence
        # about the critic's prompt, and the prompt is what is being measured.
        recorder.record_failure(exc, scope="night.critique.ranking")


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
    artifact_root: Path | None = None,
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
    resolved_night = night_of or datetime.now(UTC).strftime("%Y-%m-%d")
    run_id = repo.insert_run(
        entry_id=entry_id,
        night_of=resolved_night,
        effective_policy=str(resolution.effective_policy),
        policy_source=str(resolution.policy_source),
        compute_profile=profile,
        brain_sha=brain_sha,
    )

    # Answers the person queued last morning become tonight's input, and are
    # marked consumed so a decision stops looking pending once a run has taken
    # it. Without this the `queued-for-tonight` status is a promise the loop
    # never keeps — the answer sits forever and the night never sees it.
    answers = _take_queued_answers(repo, run_id)

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
                answers=answers,
                policy=str(resolution.effective_policy),
                completed=completed,
                results=results,
                retrieved=retrieved,
                brain=brain,
                entry_id=entry_id,
                night_of=resolved_night,
                artifact_root=artifact_root,
            )
            results[stage.name] = result
            ordered.append(result)
            if stage.name == "critique" and result.status == COMPLETE:
                _rank_the_builds(repo, recorder, results, result.text)
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

    return NightResult(
        entry_id=entry_id,
        run_id=run_id,
        outcome=outcome,
        stages=ordered,
        effective_policy=str(resolution.effective_policy),
    )
