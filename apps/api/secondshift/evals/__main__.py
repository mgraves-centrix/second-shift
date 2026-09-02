"""Record and score eval baselines.

    python -m secondshift.evals seed              # load candidates, inactive
    python -m secondshift.evals activate a b c    # choose the set
    python -m secondshift.evals baseline          # fix inputs; no judge needed
    python -m secondshift.evals status            # what is pinned, against the file
    python -m secondshift.evals summarize <id>

Scoring is deliberately absent from this entry point until a judge is chosen and
a generating provider is configured. Recording a baseline needs neither, which is
the whole reason the two are separable — the inputs can be fixed today and
scored when a model exists.
"""

from __future__ import annotations

import argparse
import os
import sys

from ..brain.repo import BrainRepo, BrainUnavailable
from ..db.connection import connect
from ..db.migrate import migrate
from ..db.repository import Repository
from .content import Rubric, load_prompts, load_rubric
from .runner import EvalRunner

DEFAULT_DB = os.path.expanduser("~/second-shift-data/second-shift.db")
DEFAULT_CANDIDATES = "config/evals/candidates.md"
DEFAULT_RUBRIC = "config/evals/rubric.md"


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
        state = "awaiting scoring" if run.awaiting else f"judged by {run.judge_model}"
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


def _dispatch(args, runner: EvalRunner, rubric: Rubric) -> int:
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
        for prompt in summary.prompts:
            print(f"  {prompt.slug:34s} mean {prompt.mean:5.2f}  sd {prompt.spread:4.2f}"
                  f"  n={len(prompt.samples)}")
        if summary.prompts:
            print(f"  overall mean {summary.mean:.2f}")
        return 0

    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="secondshift.evals")
    parser.add_argument("command", choices=["seed", "activate", "baseline", "summarize", "status"])
    parser.add_argument("args", nargs="*")
    parser.add_argument("--db", default=os.environ.get("SECOND_SHIFT_DB", DEFAULT_DB))
    parser.add_argument("--brain", default=None)
    parser.add_argument("--candidates", default=DEFAULT_CANDIDATES)
    parser.add_argument("--rubric", default=DEFAULT_RUBRIC)
    parser.add_argument("--week-of", default="")
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args(argv)

    # Closed on every path. An entry point that leaks its connection is a
    # nuisance in a shell and a failure under a test runner, which is why
    # nothing exercised this function until now.
    conn = connect(args.db)
    try:
        migrate(conn)
        runner = EvalRunner(
            Repository(conn), brain=BrainRepo(args.brain), samples=args.samples
        )
        return _dispatch(args, runner, load_rubric(args.rubric))
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
