"""What happened overnight, assembled from rows rather than narrated by a model.

Two steps, deliberately separate:

    runs + run_stages + artifacts + failures ──> Briefing (facts)
                                        Briefing ──> interviewer ──> decisions

The facts are assembled here, deterministically and with no model call. That is
principle 3 in the structure: if the interviewer cannot run, the morning still
shows what the night produced. A design where the model produces the whole
briefing renders an error on exactly the morning that matters most.

**The delta boundary is the most recently *answered* decision.** Rendering a
briefing consumes nothing; only acting does. The three mornings this was decided
against are in the proposal, and the short version is that a delta since the last
*night* silently drops the night you never read, while a delta since you last
*opened* it loses a briefing because somebody glanced at their phone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..db.repository import Repository

#: Statuses that mean the person acted. Deferring is one of them: choosing to
#: put something off is a decision, and the prompt names it a first-class
#: outcome rather than an absence of one.
ACTED_ON = ("decided", "deferred", "queued-for-tonight", "obsolete")


@dataclass(frozen=True, slots=True)
class StageLine:
    """One stage, as the morning reports it.

    `status` is what distinguishes skipped from failed, and that distinction is
    the load-bearing one: a morning that collapses both into "did not run" has
    thrown away the half that says whether anything is wrong.

    `reason` is recovered from the `failures` ledger, so it is present for a
    failed stage and **absent for a skipped one** — `run_stages` has no reason
    column, and `night-pipeline` returns the skip reason in memory without
    persisting it. That is a real gap, recorded rather than papered over with a
    field that is always `None`: see this change's tasks. A skipped stage
    therefore reports *that* it was skipped and not *why*, which is honest, and
    the common skips (`local-only`, no credential) are derivable from the run's
    own policy and the deployment's configuration.
    """

    stage: str
    status: str
    reason: str | None = None
    artifacts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NightLine:
    """One run, as the morning reports it."""

    run_id: str
    entry_id: str
    night_of: str
    outcome: str | None
    effective_policy: str
    stages: tuple[StageLine, ...] = ()

    @property
    def completed(self) -> tuple[StageLine, ...]:
        return tuple(s for s in self.stages if s.status == "complete")


@dataclass(frozen=True, slots=True)
class Question:
    """One open decision, as the morning asks it."""

    decision_id: str
    entry_id: str
    question: str
    rationale: str | None
    blocking_stage: str | None
    #: True where the entry this was raised against is `local-only`, which is
    #: exactly the set of questions whose answer could authorize sending the
    #: idea off the machine — `resolve_policy` widens `local-only` and nothing
    #: else, so on a `cloud-assisted` entry there is nothing left to widen.
    #:
    #: It over-warns on purpose. Answering *deferred* or *obsolete* on a marked
    #: question sends nothing anywhere, and marking only the answer that
    #: authorizes is not derivable: `decisions` has no column separating "yes,
    #: take this one to the cloud" from any other queued answer. Between warning
    #: about a harmless answer and staying silent about a harmful one, principle
    #: 2 takes the first.
    #:
    #: It travels with the question rather than being a screen's job to
    #: remember, because a warning that lives in a component is one the next
    #: component does not inherit. The name overstates — what is true is *an
    #: answer here is the only thing that could authorize it* — so the wording a
    #: person reads lives beside the rule in `apps/web/lib/morning.ts` rather
    #: than being written from this identifier.
    will_leave_the_machine: bool = False


@dataclass(frozen=True, slots=True)
class Briefing:
    """The morning, in the order a person reads it."""

    nights: tuple[NightLine, ...] = ()
    questions: tuple[Question, ...] = ()
    #: Set when the interviewer could not run. The facts above are still real —
    #: principle 3 — and this says why there are no questions beside them.
    interviewer_error: str | None = None

    @property
    def is_empty(self) -> bool:
        return not self.nights and not self.questions


def boundary_ms(repo: Repository) -> int:
    """The instant the last interview happened, or 0 if none ever has.

    Derived rather than stored. An `interviews` table would be a second thing
    that can disagree with `decisions`, with the stored one winning silently —
    the same argument that keeps counters as views.
    """
    placeholders = ",".join("?" for _ in ACTED_ON)
    row = repo.connection.execute(
        f"SELECT MAX(answered_at_ms) m FROM decisions "
        f"WHERE answered_at_ms IS NOT NULL AND status IN ({placeholders})",
        ACTED_ON,
    ).fetchone()
    return int(row["m"] or 0)


def assemble(repo: Repository, *, include_synthetic: bool = False) -> Briefing:
    """Every run since the last answered decision, with its stages and questions.

    Runs no model. A briefing that needed one would be a briefing that could
    fail, and the one morning it failed would be the morning after the night it
    was most needed for.

    `include_synthetic` is principle 5's hook and the judge instance is what
    passes it: that deployment runs this same code over seeded rows, and a
    briefing that filtered them would show a judge an empty morning. It is set
    from the deployment's own `is_synthetic`, never from a request — the same
    rule capture already follows, and for the same reason.
    """
    since = boundary_ms(repo)
    synthetic = "" if include_synthetic else "AND r.is_synthetic = 0"
    runs = repo.connection.execute(
        f"SELECT * FROM runs r WHERE r.started_at_ms > ? {synthetic} "
        "ORDER BY r.started_at_ms",
        (since,),
    ).fetchall()

    nights = tuple(_night_line(repo, run) for run in runs)
    questions = tuple(_open_questions(repo))
    return Briefing(nights=nights, questions=questions)


def _night_line(repo: Repository, run) -> NightLine:
    by_stage: dict[str, list[str]] = {}
    for artifact in repo.artifacts_for_run(run["id"]):
        by_stage.setdefault(artifact["stage"], []).append(artifact["path"])

    reasons = _failure_reasons(repo, run["id"])
    stages = tuple(
        StageLine(
            stage=s["stage"],
            status=s["status"],
            reason=reasons.get(s["stage"]),
            artifacts=tuple(by_stage.get(s["stage"], ())),
        )
        for s in repo.stages_for_run(run["id"])
    )
    return NightLine(
        run_id=run["id"],
        entry_id=run["entry_id"],
        night_of=run["night_of"],
        outcome=run["outcome"],
        effective_policy=run["effective_policy"],
        stages=stages,
    )


def _failure_reasons(repo: Repository, run_id: str) -> dict[str, str]:
    """Why each failed stage failed, read from the ledger.

    The night records failures scoped `night.<stage>`, and `signature()` embeds
    that scope, so the stage is recoverable without a column on `run_stages`.
    Matched on the signature rather than parsed out of the message, because the
    message is the exception's own text and its shape is not ours to rely on.
    """
    reasons: dict[str, str] = {}
    for row in repo.connection.execute(
        "SELECT signature, message FROM failures WHERE run_id = ? ORDER BY ts_ms",
        (run_id,),
    ):
        parts = row["signature"].split(":")
        scope = parts[1] if len(parts) > 1 else ""
        if scope.startswith("night."):
            stage = scope.removeprefix("night.").split(".")[0]
            reasons.setdefault(stage, row["message"])
    return reasons


def _open_questions(repo: Repository):
    """Every open question, joined to the policy its entry was captured under.

    The join is what makes `will_leave_the_machine` mean anything. Without it
    every question was constructed with the field left at its default, so it had
    never been `True` on any morning — while `morning-interview`'s spec claimed
    the briefing marks the questions whose answer sends an idea off the machine.
    The one test that named the field asserted the key was present in the JSON,
    which a permanently `false` value satisfies.

    `blocking_stage` is read here and is presently always `NULL`:
    `Repository.insert_decision` accepts it and `raise_questions` never passes
    it. No spec claims otherwise, so it is an unset field rather than a false
    claim, and closing it means changing the interviewer's output format.
    """
    rows = repo.connection.execute(
        "SELECT d.*, e.default_policy FROM decisions d "
        "JOIN entries e ON e.id = d.entry_id "
        "WHERE d.status = 'open' ORDER BY d.raised_at_ms, d.id"
    ).fetchall()
    for row in rows:
        yield Question(
            decision_id=row["id"],
            entry_id=row["entry_id"],
            question=row["question"],
            rationale=row["rationale"],
            blocking_stage=row["blocking_stage"],
            will_leave_the_machine=row["default_policy"] == "local-only",
        )
