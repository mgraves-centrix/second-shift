"""What a stage leaves behind: its files, its variants, its brain commit.

Split out of `run.py`, which walks the stages and closes the run. Everything
here lands a stage's output somewhere a morning can open it, and the research
stage lives here too because a search's only product is the digest it writes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..artifacts.store import VARIANT_KINDS, ArtifactWriteFailed, write_artifact
from ..artifacts.variants import write_variants
from ..brain.beliefs import apply_beliefs, parse_beliefs
from ..brain.repo import BrainRepo, BrainUnavailable
from ..db.connection import now_ms
from ..db.repository import Repository
from ..telemetry.recorder import Recorder
from .events import _stage_event
from .research import run_research
from .stages import Stage

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


def run_research_stage(
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
    started_at_ms: int | None = None,
) -> StageResult:
    """The one stage that talks outward. Skips are reasons, not failures.

    A skip here is `skipped`, never `failed`: no credential and a `local-only`
    policy are both facts about the deployment rather than something that broke,
    and a morning that reported them as failures would be reporting a defect
    that does not exist. A quota refusal *is* a failure, and a typed one.

    `started_at_ms` is the stage's own start, so the `stage_end` this writes has
    a span. The caller opened the stage and recorded `stage_start`; every exit
    here has to close it, or the timeline shows research beginning and never
    ending — which is exactly what the first version of this did.
    """
    def _end(label: str, severity: str = "info") -> None:
        _stage_event(
            recorder,
            run_id=run_id,
            lane="system",
            kind="stage_end",
            label=label,
            severity=severity,
            duration_ms=(now_ms() - started_at_ms) if started_at_ms else None,
        )

    try:
        outcome = run_research(
            recorder, policy=policy, entry_text=entry_text, run_id=run_id
        )
    except Exception as exc:  # noqa: BLE001 - classified and recorded, not swallowed
        recorder.record_failure(exc, scope="night.research", run_id=run_id)
        repo.complete_run_stage(stage_id, status=FAILED)
        _stage_event(
            recorder, run_id=run_id, lane=stage.role, kind="error",
            label=f"research failed — {str(exc) or type(exc).__name__}",
            severity="error",
        )
        _end("research failed", "error")
        return StageResult(stage.name, FAILED, reason=str(exc) or type(exc).__name__)

    if not outcome.searched:
        repo.complete_run_stage(stage_id, status=SKIPPED)
        _end(f"research skipped — {outcome.reason}", "warn")
        return StageResult(stage.name, SKIPPED, reason=outcome.reason)

    # The digest lands like any other stage's output. `produced_by_invocation_id`
    # is null here and correctly so: a search is a tool call, not an agent
    # invocation, and claiming one would point at a row that does not exist.
    try:
        landed, _ = write_output(
            repo,
            stage,
            outcome.digest,
            run_id=run_id,
            entry_id=entry_id,
            night_of=night_of,
            invocation_id=invocation_id,
            root=artifact_root,
        )
    except Exception as exc:  # noqa: BLE001 - recorded; a stage never raises
        recorder.record_failure(exc, scope="night.research.artifact", run_id=run_id)
        repo.complete_run_stage(stage_id, status=FAILED)
        _end("research produced nothing", "error")
        return StageResult(stage.name, FAILED, reason=str(exc))

    repo.complete_run_stage(stage_id, status=COMPLETE)
    _stage_event(
        recorder, run_id=run_id, lane=stage.role, kind="search",
        label="search returned results",
    )
    for _ in landed:
        _stage_event(
            recorder, run_id=run_id, lane=stage.role, kind="file_write",
            label=f"{stage.artifact_kind or stage.name} written",
        )
    _end("research complete")
    return StageResult(
        stage.name, COMPLETE, text=outcome.digest, artifacts=tuple(landed)
    )


def write_output(
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
            contents=variant_bodies(text),
            produced_by_invocation_id=invocation_id,
            root=root,
        )
        if not produced.written:
            # `write_variants` records each failed write and returns normally,
            # which is right for one bad variant among five and wrong for all of
            # them: a stage closed `complete` with nothing on disk is a morning
            # promising work it cannot open.
            raise ArtifactWriteFailed(
                f"no {stage.artifact_kind} variant could be written "
                f"({len(produced.failed)} attempted)"
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


def variant_bodies(text: str) -> list[str]:
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


def write_to_brain(
    brain: BrainRepo, run_id: str, text: str
) -> tuple[int | None, str | None]:
    """Append this night's distillation and commit it. Never raises.

    The beliefs it proposed are applied in the same commit, so one night is one
    revision of what the system thinks and `git show` reads as an argument: the
    night's reasoning, and the lines of the profile it changed.

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
        revised = apply_beliefs(brain, parse_beliefs(text))
        summary = f"night: distill {run_id}"
        if revised:
            summary += f"\n\nRevised {', '.join(revised)}."
        sha = brain.commit_paths(
            [str(path.relative_to(brain.path)), *revised], summary
        )
    except (BrainUnavailable, OSError):
        return None, None
    return (now_ms(), sha) if sha else (None, None)
