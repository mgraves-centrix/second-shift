"""Record and score eval baselines.

    python -m secondshift.evals seed              # load candidates, inactive
    python -m secondshift.evals activate a b c    # choose the set
    python -m secondshift.evals baseline          # fix inputs; no judge needed
    python -m secondshift.evals status            # what is pinned, against the file
    python -m secondshift.evals summarize <id>
    python -m secondshift.evals score <id>       # generate and grade

Scoring was absent from this entry point until 10 Oct, while no judge existed
and `EvalRunner.score` was reachable only from the test suite. Recording a
baseline needs neither a judge nor a generating provider, which is the whole
reason the two are separable — the inputs can be fixed on day 3 and scored when
a model exists.

`score` refuses rather than substituting, at every point where it could
substitute: no judge configured, no local reasoner bound, no pinned version. A
stub judge that reached the real curve would be the one defect here that cannot
be withdrawn, because the claim is a week-1 to week-8 comparison and there is no
way to tell afterwards which rows came from where.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from ..agents.invoke import invoke
from ..agents.roster import discover, register
from ..brain.repo import BrainRepo, BrainUnavailable
from ..config import Profile, eval_settings, resolve_profile, synthetic_flag
from ..db.connection import connect
from ..db.migrate import migrate
from ..db.repository import Repository
from ..providers.registry import LocalReasonerNotConfigured, Registry
from ..telemetry.pricing import PricingTable
from ..telemetry.recorder import Recorder
from .content import Rubric, load_prompts, load_rubric, load_threshold
from .judge import ModelJudge
from .runner import (
    NO_IMPROVEMENT_SHOWN,
    AlreadyScored,
    DeploymentMismatch,
    EvalRunner,
    NotComparable,
)

#: The policy every call in a scoring run carries. Not configurable, and not an
#: argument. ADR 0010 makes brain topic files `local-only`, and an eval answer is
#: generated from them: treating the output as less restricted than its most
#: restricted input would launder the policy. ADR 0015 records why the judge is
#: local, and moving it means superseding 0010 with an argument rather than
#: setting a value here.
POLICY = "local-only"

DEFAULT_DB = os.path.expanduser("~/second-shift-data/second-shift.db")

#: Where `config/` sits relative to this file, in a clone and in the deployed
#: tree alike: `apps/api/secondshift/evals/` is four levels below it in both.
#: These resolved against the working directory until 17 Oct, so `status` run
#: over SSH on the always-on machine died with a traceback naming a relative
#: path — the one place this command is meant to be run.
_CONTENT = Path(__file__).resolve().parents[4] / "config" / "evals"
DEFAULT_CANDIDATES = str(_CONTENT / "candidates.md")
DEFAULT_RUBRIC = str(_CONTENT / "rubric.md")
DEFAULT_THRESHOLD = str(_CONTENT / "threshold.md")


def _status(runner: EvalRunner, rubric: Rubric) -> int:
    """The active set, and every recorded run beside the rubric on disk.

    The exit code is part of the report. A run pinned to a rubric that is not the
    file on disk went unnoticed because `status` printed only the hash of the file
    it had itself just read — the one value that cannot reveal the disagreement —
    and exited zero either way.
    """
    active = runner.active_prompts()
    print(f"{len(active)} active prompt{'' if len(active) == 1 else 's'}")
    for _id, slug, _prompt in active:
        print(f"  {slug}")

    print(f"rubric on disk  {rubric.sha[:12]}  {rubric.path}")

    runs = runner.recorded_runs()
    if not runs:
        print("no recorded run has pinned it yet")
        return 0

    print(f"{len(runs)} recorded run{'' if len(runs) == 1 else 's'}")
    for run in runs:
        if run.interrupted:
            state = (f"interrupted with {run.results} result"
                     f"{'' if run.results == 1 else 's'}; cannot be scored, "
                     "record a new baseline")
        elif run.awaiting:
            state = "awaiting scoring"
        else:
            state = f"judged by {run.judge_model}"
        agrees = run.rubric_sha == rubric.sha
        print(
            f"  {run.eval_run_id}  week {run.week_of}"
            f"  rubric {run.rubric_sha[:12]}  brain {run.brain_sha[:12]}  {state}"
            f"{'' if agrees else '  <- not the rubric on disk'}"
        )

    drifted = [run for run in runs if run.rubric_sha != rubric.sha]
    if not drifted:
        print("every recorded run pinned the rubric on disk")
        return 0

    print()
    for run in drifted:
        print(
            f"run {run.eval_run_id} pinned rubric {run.rubric_sha[:12]}, and "
            f"{rubric.path} hashes to {rubric.sha[:12]}"
        )
    print(
        "scoring is refused while they disagree, because grading a run against a "
        "rubric it never used produces a number carrying a hash that did not grade "
        "it. Restore the rubric these runs pinned, or record a new baseline under "
        "the rubric on disk — a rubric is superseded, never edited in place."
    )
    return 1


def _dispatch(args, runner: EvalRunner, rubric: Rubric, repo: Repository) -> int:
    if args.command == "seed":
        added = runner.load_candidates(load_prompts(args.candidates), rubric)
        print(f"loaded {added} new candidate prompts, all inactive")
        print("choose with: python -m secondshift.evals activate <slug> <slug> ...")
        return 0

    if args.command == "activate":
        if not args.args:
            print("name at least one prompt slug", file=sys.stderr)
            return 2
        print(f"activated {runner.activate(args.args)} prompts")
        return 0

    if args.command == "status":
        return _status(runner, rubric)

    if args.command == "baseline":
        if not runner.active_prompts():
            print("no active prompts; nothing to baseline", file=sys.stderr)
            return 1
        try:
            run_id = runner.record_baseline(week_of=args.week_of or "unset", rubric=rubric)
        except BrainUnavailable as exc:
            print(f"baseline refused: {exc}", file=sys.stderr)
            return 1
        summary = runner.summarize(run_id)
        print(f"baseline {run_id}")
        print(f"  brain  {summary.brain_sha}")
        print(f"  rubric {summary.rubric_sha[:12]}")
        print("  awaiting scoring — inputs are fixed and cannot drift")
        return 0

    if args.command == "summarize":
        if not args.args:
            print("name an eval run id", file=sys.stderr)
            return 2
        summary = runner.summarize(args.args[0])
        print(f"run {summary.eval_run_id} judge={summary.judge_model} "
              f"complete={summary.complete}")
        # What produced the outputs, not only what graded them. A run's judge
        # was always printed here and its generator never was, which is the
        # asymmetry that let the curve compare two models as two brain states.
        print(f"  generated by {summary.generators_text()}")
        for prompt in summary.prompts:
            print(f"  {prompt.slug:34s} mean {prompt.mean:5.2f}  sd {prompt.spread:4.2f}"
                  f"  n={len(prompt.samples)}")
        if summary.prompts:
            print(f"  overall mean {summary.mean:.2f}")
        return 0

    if args.command == "score":
        if not args.args:
            print("name an eval run id", file=sys.stderr)
            return 2
        return _score(runner, repo, args.args[0], rubric)

    if args.command == "curve":
        return _curve(runner, args.args, load_threshold(args.threshold))

    return 2


def _curve(runner: EvalRunner, ids: list[str], threshold) -> int:
    """The comparison the submission rests on, or the reason there isn't one.

    With no arguments it takes the oldest and newest scored runs, because
    picking two identifiers by hand out of a table on another machine is how the
    wrong pair gets compared.
    """
    if len(ids) == 2:
        earlier_id, later_id = ids
    elif ids:
        print("curve takes two eval run ids, or none to take the oldest and newest",
              file=sys.stderr)
        return 2
    else:
        scored = [r for r in runner.recorded_runs() if not r.awaiting]
        if len(scored) < 2:
            print(f"{len(scored)} scored run(s): nothing to compare yet. The curve is "
                  "a comparison, and a comparison needs two.", file=sys.stderr)
            return 1
        earlier_id, later_id = scored[0].eval_run_id, scored[-1].eval_run_id

    try:
        curve = runner.curve(earlier_id, later_id, threshold=threshold)
    except (NotComparable, ValueError) as exc:
        print(f"not comparable: {exc}", file=sys.stderr)
        return 1

    print(f"{curve.earlier.eval_run_id}  brain {curve.earlier.brain_sha[:12]}"
          f"  mean {curve.earlier.mean:5.2f}")
    print(f"{curve.later.eval_run_id}  brain {curve.later.brain_sha[:12]}"
          f"  mean {curve.later.mean:5.2f}")
    print(f"judged by {curve.earlier.judge_model}, rubric {curve.earlier.rubric_sha[:12]}")
    print()
    for delta in curve.dimensions:
        print(f"  {delta.dimension:16s} {delta.earlier:5.2f} -> {delta.later:5.2f}"
              f"  {delta.difference:+5.2f}")
    print()
    # The spread is never optional. A difference shown without it is the version
    # that gets screenshotted, and it is not evidence.
    print(f"  difference {curve.difference:+.2f}  against a spread of {curve.spread:.2f}")
    print(f"  {curve.agreeing_dimensions} of {len(curve.dimensions)} dimensions moved the same way")
    if curve.moved:
        print("  larger than the sampling spread")
    else:
        print("  inside the sampling spread: not shown to have moved")

    # Paired, which is what the bar is applied to. The line above is the pooled
    # view and stays because it is the one a reader checks by eye.
    print()
    for delta in curve.prompts:
        print(f"  {delta.slug:34s} {delta.earlier:5.2f} -> {delta.later:5.2f}"
              f"  {delta.difference:+5.2f}")
    print(f"\n  per prompt {curve.paired_difference:+.2f}"
          f"  standard error {curve.standard_error:.2f}"
          f"  {curve.agreeing_prompts} of {len(curve.prompts)} agreeing")
    # The hash travels with the verdict, so a threshold edited after the result
    # is visible in the one place somebody reads the result.
    print(f"  bar: {threshold.standard_errors:g} standard errors and "
          f"{threshold.agreeing_share:.0%} agreeing, fixed {threshold.fixed_on} "
          f"({threshold.sha[:12]})")
    print(f"\n  VERDICT: {curve.verdict}")
    if curve.verdict == NO_IMPROVEMENT_SHOWN:
        print("  — which is not the same as the brain having learned nothing;")
        print("    six prompts cannot resolve a small effect from none.")
    return 0


def _score(
    runner: EvalRunner, repo: Repository, eval_run_id: str, rubric: Rubric
) -> int:
    """Generate a run's answers and grade them, or refuse and say why.

    Every refusal here is a substitution not made. The registry binds an echo
    reasoner on the `cloud` profile, `StubJudge` exists for exercising the
    runner, and either of them reaching a real run writes scores that look like
    every other score in the table. Unlike a bad artifact, a scored eval run
    cannot be withdrawn: the claim is a week-1 to week-8 comparison, and nothing
    afterwards can tell which rows came from where.
    """
    settings = eval_settings()
    missing = [
        name
        for name, value in (
            ("evals.judge_version", settings.judge_version),
            ("evals.generating_role", settings.role),
        )
        if not value
    ]
    if missing:
        print(
            f"not scoring: {' and '.join(missing)} is not set in config/models.toml. "
            "Refusing to score under a pin nobody chose — a run recorded against "
            "the wrong version is in the curve.",
            file=sys.stderr,
        )
        return 2

    resolved = resolve_profile()
    if resolved.profile is Profile.CLOUD:
        # The same refusal the night makes, for a sharper reason. A night run
        # against the echo produced artifacts somebody would eventually read and
        # disbelieve. Scoring against it produces numbers that are the evidence.
        reason = resolved.degradation_reason or "the profile resolved to cloud"
        print(
            f"not scoring: no local reasoner can do the work ({reason}). The "
            "judge runs local-only by ADR 0015, and the registry binds an echo "
            "here — scoring against it would put fabricated numbers in the curve.",
            file=sys.stderr,
        )
        return 2

    recorder = Recorder(
        repo, pricing=PricingTable.load(), compute_profile=str(resolved.profile)
    )
    try:
        reasoner = Registry(recorder).bind(str(resolved.profile)).reasoner
    except LocalReasonerNotConfigured as exc:
        print(f"not scoring: {exc}", file=sys.stderr)
        return 2

    agents = register(repo)
    prompts = discover()
    if settings.role not in agents or settings.role not in prompts:
        print(
            f"not scoring: no prompt registered for role {settings.role!r}",
            file=sys.stderr,
        )
        return 2

    def generate(*, prompt: str, brain, sample: int):
        """One answer, produced the way the product produces work.

        Through the agent path rather than a composition written for evaluation:
        an improvement measured in a harness is an improvement in the harness.
        The brain arrives as the topic files at the run's pinned commit, which is
        what `EvalRunner.score` reads and what makes the number a week-1 number.
        """
        turn = invoke(
            recorder,
            reasoner,
            role=settings.role,
            agent_id=agents[settings.role],
            prompt_path=prompts[settings.role].path,
            task=prompt,
            policy=POLICY,
            context=_brain_context(brain),
        )
        return _Generated(text=turn.text, model_call_id=turn.model_call_id)

    judge = ModelJudge(reasoner, policy=POLICY, version=settings.judge_version)
    try:
        summary = runner.score(
            eval_run_id, judge=judge, generate=generate, rubric=rubric
        )
    except (DeploymentMismatch, AlreadyScored) as exc:
        print(f"not scoring: {exc}", file=sys.stderr)
        return 2

    print(f"run {summary.eval_run_id} judge={summary.judge_model} "
          f"complete={summary.complete}")
    print(f"  generated by {summary.generators_text()}")
    print(f"  prompt       {summary.prompt_versions_text()}")
    for prompt_summary in summary.prompts:
        print(f"  {prompt_summary.slug:34s} mean {prompt_summary.mean:5.2f}"
              f"  sd {prompt_summary.spread:4.2f}  n={len(prompt_summary.samples)}")
    if summary.prompts:
        print(f"  overall mean {summary.mean:.2f}")
    if not summary.complete:
        # Non-zero, because an incomplete run is not a scored run: the curve
        # refuses it, and an operator who saw zero would not know that yet.
        print("  incomplete — some samples failed; see the failure ledger",
              file=sys.stderr)
        return 1
    return 0


@dataclass(frozen=True, slots=True)
class _Generated:
    """What `generate` owes the runner: the text, and the call behind it."""

    text: str
    model_call_id: str | None


def _brain_context(brain) -> str:
    """The brain's topic files as one block of context.

    Labeled by file rather than concatenated, because the rubric scores *voice*
    and *fit* — a model that cannot tell the style guide from the profile cannot
    be expected to apply one and not the other.
    """
    parts = [
        f"--- {name} ---\n{text.strip()}"
        for name, text in (
            ("profile.md", brain.profile),
            ("style-guide.md", brain.style_guide),
            *((f"skills/{n}", s) for n, s in sorted(brain.skills.items())),
        )
        if text.strip()
    ]
    return "\n\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="secondshift.evals")
    parser.add_argument(
        "command",
        choices=[
            "seed", "activate", "baseline", "summarize", "status", "score", "curve"
        ],
    )
    parser.add_argument("args", nargs="*")
    parser.add_argument("--db", default=os.environ.get("SECOND_SHIFT_DB", DEFAULT_DB))
    parser.add_argument("--brain", default=None)
    parser.add_argument("--candidates", default=DEFAULT_CANDIDATES)
    parser.add_argument("--rubric", default=DEFAULT_RUBRIC)
    parser.add_argument("--threshold", default=DEFAULT_THRESHOLD)
    parser.add_argument("--week-of", default="")
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args(argv)

    # Closed on every path. An entry point that leaks its connection is a
    # nuisance in a shell and a failure under a test runner, which is why
    # nothing exercised this function until now.
    conn = connect(args.db)
    try:
        migrate(conn)
        repo = Repository(conn)
        runner = EvalRunner(
            repo,
            brain=BrainRepo(args.brain),
            samples=args.samples,
            # Server-derived, never a flag on this command. A judge deployment
            # that scored itself into the real curve would be unrecoverable:
            # the whole claim is a week-1 to week-8 comparison, and there is no
            # way to tell afterwards which rows came from where.
            is_synthetic=synthetic_flag(),
        )
        return _dispatch(args, runner, load_rubric(args.rubric), repo)
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
