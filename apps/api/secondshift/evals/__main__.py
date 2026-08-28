"""Record and score eval baselines.

    python -m secondshift.evals seed              # load candidates, inactive
    python -m secondshift.evals activate a b c    # choose the set
    python -m secondshift.evals baseline          # fix inputs; no judge needed
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
from .content import load_prompts, load_rubric
from .runner import EvalRunner

DEFAULT_DB = os.path.expanduser("~/second-shift-data/second-shift.db")
DEFAULT_CANDIDATES = "config/evals/candidates.md"
DEFAULT_RUBRIC = "config/evals/rubric.md"


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

    conn = connect(args.db)
    migrate(conn)
    runner = EvalRunner(Repository(conn), brain=BrainRepo(args.brain), samples=args.samples)
    rubric = load_rubric(args.rubric)

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
        active = runner.active_prompts()
        print(f"{len(active)} active prompts; rubric {rubric.sha[:12]}")
        for _id, slug, _p in active:
            print(f"  {slug}")
        awaiting = runner.awaiting_scoring()
        print(f"{len(awaiting)} runs awaiting scoring")
        return 0

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


if __name__ == "__main__":
    raise SystemExit(main())
