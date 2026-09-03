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
from ..airlock.policy import Policy
from ..brain.repo import BrainRepo, BrainUnavailable
from ..morning import assemble, raise_questions
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


def _ask_about(repo, recorder, providers, result, agents, prompts, entry_id) -> int:
    """Run the interviewer over the night just finished. Never fails the run.

    A night that produced work and could not phrase a question is still a night
    that produced work — principle 3 again. The failure is recorded and the
    morning shows the facts with nothing to ask.
    """
    if result.quarantined or result.run_id is None:
        return 0
    try:
        raised = raise_questions(
            repo,
            recorder,
            providers.reasoner,
            assemble(repo),
            agent_id=agents["interviewer"],
            prompt_path=prompts["interviewer"],
            entry_id=entry_id,
            policy=result.effective_policy or str(Policy.LOCAL_ONLY),
            run_id=result.run_id,
        )
    except Exception as exc:  # noqa: BLE001 - recorded, and the night still stands
        recorder.record_failure(exc, scope="night.interviewer")
        return 0
    return len(raised)


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

            # The interviewer runs here, at the end of the night, and this is
            # what makes the morning have anything to ask. It is not an evening
            # interview: nobody is spoken to now. The questions sit as `open`
            # decisions until the person opens the morning, which is exactly the
            # loop ADR 0005 settled — capture stays instant, the night does the
            # work, and the asking happens over coffee.
            #
            # Without it `raise_questions` had no caller outside its tests, so
            # the briefing was structurally incapable of containing a question.
            asked = _ask_about(
                repo, recorder, providers, result, agents, prompts, row["id"]
            )
            if asked:
                print(f"{' ' * 26}{asked} question(s) raised for the morning")

        for row, reason in repo.ineligible_entries():
            print(f"{row['id']}  not dispatched  {reason}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
