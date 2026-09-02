"""`python -m secondshift.night run` — start a night by hand.

A separate entry point rather than an API route, for the same reason
`secondshift.brain` is one: this is an operator action on the machine, not
something a phone asks for. It must work at 2am when the API is the thing that
is wrong.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from ..agents.roster import discover, register
from ..brain.repo import BrainRepo, BrainUnavailable
from ..config import ENV_DB, Profile, resolve_profile
from ..db.connection import connect
from ..db.migrate import migrate
from ..db.repository import Repository
from ..artifacts.store import artifact_root
from ..providers.registry import LocalEmbedderNotConfigured, Registry
from ..providers.vllm_embed import EmbedderUnavailable
from ..retrieval.index import RetrievalIndex, assemble_context, collect_documents
from ..telemetry.pricing import PricingTable
from ..telemetry.recorder import Recorder
from .run import run_entry


def _default_db() -> str:
    return os.environ.get(ENV_DB) or os.path.expanduser(
        "~/second-shift-data/second-shift.db"
    )


def _retrieve(repo, providers, brain, entry) -> str:
    """Context for the brief stage, or empty when the index cannot be built.

    Attempted, never required. The embedder is a separate server on its own
    port; a night must not be lost because it is down. An empty return is not
    silent — `run_entry` hands the brief stage a note saying it had no memory to
    draw on, so a memory-less brief is distinguishable from a memory-informed
    one that found nothing.

    The exceptions caught are named rather than blanket: an embedder that is
    down, timing out, unconfigured, or a brain that is not there. Anything else
    is a real defect and should propagate rather than quietly costing the run
    its memory on every future night.
    """
    if brain is None:
        return ""
    try:
        index = RetrievalIndex(providers.embedder)
        index.load(collect_documents(repo, brain))
        pieces = assemble_context(
            index, entry["raw_text"] or "", policy=entry["default_policy"]
        )
    except (EmbedderUnavailable, LocalEmbedderNotConfigured, BrainUnavailable):
        return ""
    # Rendered here, with the source on each piece: a brief that cites the brain
    # should be traceable to the file it came from without a join.
    return "\n\n".join(f"### {p.source}\n\n{p.text}" for p in pieces)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m secondshift.night")
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--db", default=_default_db())
    parser.add_argument(
        "--entry", default=None, help="dispatch one entry rather than all eligible"
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    conn = connect(args.db)
    try:
        migrate(conn)
        repo = Repository(conn)
        resolved = resolve_profile()
        recorder = Recorder(
            repo, pricing=PricingTable.load(), compute_profile=str(resolved.profile)
        )
        providers = Registry(recorder).bind(str(resolved.profile))
        agents = register(repo)
        prompts = {role: p.path for role, p in discover().items()}
        # Passed only when it is genuinely there. `distill` writing to a brain
        # that is not a git repository would leave a file nothing commits.
        brain = BrainRepo()
        brain = brain if brain.available else None

        rows = repo.dispatch_eligible_entries()
        if args.entry:
            rows = [r for r in rows if r["id"] == args.entry]
            if not rows:
                print(f"{args.entry} is not eligible for dispatch", file=sys.stderr)
                return 1

        # `local-only` is honored only where the probe confirmed a local stack.
        # On `cloud` the registry binds a placeholder reasoner, so treating it
        # as available would run a local-only idea against a stub.
        local_available = resolved.profile is not Profile.CLOUD

        for row in rows:
            result = run_entry(
                repo,
                recorder,
                providers,
                row,
                profile=str(resolved.profile),
                agents=agents,
                prompts=prompts,
                local_available=local_available,
                unavailable_reason=resolved.degradation_reason,
                brain=brain,
                brain_sha=brain.head() if brain else None,
                retrieved=_retrieve(repo, providers, brain, row),
                artifact_root=artifact_root(),
            )
            if result.quarantined:
                print(f"{result.entry_id}  quarantined  {result.quarantine_reason}")
                continue
            done = sum(1 for s in result.stages if s.status == "complete")
            print(
                f"{result.entry_id}  {result.outcome}  "
                f"{done}/{len(result.stages)} stages complete  run {result.run_id}"
            )

        for row, reason in repo.ineligible_entries():
            print(f"{row['id']}  not dispatched  {reason}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
