#!/usr/bin/env python3
"""Prove the gates can fail.

A test that has never failed is a hypothesis. Each mutation below reintroduces a
defect this project has actually shipped or nearly shipped, runs the one gate
that exists to catch it, and requires that gate to go red. The file is then
restored from the bytes read before mutating — never from git, so an
uncommitted change is never discarded.

A mutation whose `before` text no longer appears exactly once is a failure, not
a skip. Code moves, and a mutation that silently stopped applying would report
"caught" for a defect it no longer introduces.

Run from anywhere: `python3 scripts/check-mutations.py [name ...]`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = os.environ.get("GATE_PYTHON", str(ROOT / "apps/api/.venv/bin/python"))

WEB_TESTS = ["npm", "--prefix", str(ROOT / "apps/web"), "test"]
PYTEST = [PYTHON, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"]


@dataclass(frozen=True)
class Mutation:
    name: str
    why: str
    path: str
    before: str
    after: str
    gate: list[str]


MUTATIONS = [
    Mutation(
        "frame-ends-at-last-start",
        "2 Sep: a bar beginning near the end of the night overran its own frame.",
        "apps/web/lib/timeline.ts",
        "(latest, e) => Math.max(latest, e.ts_ms + (e.duration_ms ?? 0)),",
        "(latest, e) => Math.max(latest, e.ts_ms),",
        WEB_TESTS,
    ),
    Mutation(
        "no-minimum-bar-width",
        "2 Sep: a short bar rendered narrower than the tick it must be told apart from.",
        "apps/web/lib/timeline.ts",
        "w: bar ? Math.max(MIN_BAR_FRACTION, (event.duration_ms as number) / span) : 0,",
        "w: bar ? (event.duration_ms as number) / span : 0,",
        WEB_TESTS,
    ),
    Mutation(
        "lanes-by-joining",
        "2 Sep: lanes computed from events with an invocation passed a fixture in "
        "which every lane happened to have one, and dropped the night's skeleton.",
        "apps/web/lib/timeline.ts",
        "const lanes = timeline.lanes.length\n    ? timeline.lanes\n"
        "    : [...new Set(events.map((e) => e.lane))].sort();",
        "const lanes = [...new Set(events.filter((e) => e.agent_invocation_id)"
        ".map((e) => e.lane))].sort();",
        WEB_TESTS,
    ),
    Mutation(
        "stages-dropped",
        "2 Sep: a night that stopped part-way must say so, and says so from its stages.",
        "apps/web/lib/timeline.ts",
        "stages: timeline.stages,",
        "stages: [],",
        WEB_TESTS,
    ),
    Mutation(
        "playhead-percentage-transform",
        "2 Sep: the playhead moved by a percentage of its own one-pixel width and sat "
        "still while three ARIA-reading tests passed.",
        "apps/web/components/scrubber/Scrubber.tsx",
        "headRef.current.style.transform = `translateX(${position * width}px)`;",
        "headRef.current.style.transform = `translateX(${position * 100}%)`;",
        ["bash", "-c", f"npm --prefix '{ROOT}/apps/web' run build >/dev/null && "
         f"npm --prefix '{ROOT}/apps/web' run e2e"],
    ),
    Mutation(
        "answers-cross-ideas",
        "16 Sep: queued answers were taken by whichever entry ran first, carrying a "
        "local-only answer into a cloud-assisted run.",
        "apps/api/secondshift/morning/interview.py",
        '"SELECT * FROM decisions WHERE entry_id = ? AND status = \'queued-for-tonight\' "',
        '"SELECT * FROM decisions WHERE (entry_id = ? OR 1) AND status = \'queued-for-tonight\' "',
        PYTEST + [str(ROOT / "apps/api/tests/test_the_loop_closes.py")],
    ),
    Mutation(
        "identifiers-reach-the-query",
        "16 Sep: paths, assignments and mixed-case keys reached the search query.",
        "apps/api/secondshift/airlock/redact.py",
        '_IDENTIFIER_SHAPED = re.compile(r"[\\d_/\\\\=]|[a-z][A-Z]|^[A-Za-z-]{20,}$")',
        '_IDENTIFIER_SHAPED = re.compile(r"(?!)")',
        PYTEST + [str(ROOT / "apps/api/tests/test_redaction.py")],
    ),
    Mutation(
        "failure-loses-its-run",
        "16 Sep: stage failures recorded outside an invocation had no run, so the "
        "morning never said why a stage failed.",
        "apps/api/secondshift/telemetry/recorder.py",
        "run_id=run_id or (active.run_id if active else None),\n"
        "                agent_invocation_id=active.invocation_id if active else None,\n"
        "                is_synthetic=is_synthetic,\n            )\n\n    # --",
        "run_id=active.run_id if active else None,\n"
        "                agent_invocation_id=active.invocation_id if active else None,\n"
        "                is_synthetic=is_synthetic,\n            )\n\n    # --",
        PYTEST + [str(ROOT / "apps/api/tests/test_the_loop_closes.py")],
    ),
    Mutation(
        "idea-retrieves-itself",
        "17 Sep: on the always-on machine every idea's closest memory was itself, "
        "handed to the brief as earlier work.",
        "apps/api/secondshift/retrieval/index.py",
        "if _may_leave(p.policy, policy) and p.source not in exclude",
        "if _may_leave(p.policy, policy)",
        PYTEST + [str(ROOT / "apps/api/tests/test_retrieval.py")],
    ),
    Mutation(
        "drift-guesses-at-prose",
        "23 Sep: the drift checker's value is that it never guesses. A version "
        "that read bare numbers would fire on five rubric dimensions and six "
        "night stages, and a check with false positives is one people suppress.",
        "scripts/check-drift.py",
        # Anchored to the binding rather than the loop, after 16 Oct moved the
        # findall into its own statement so an unbound marker could be noticed.
        # The runner reported that itself — "its target appears 0 times; the
        # code moved" — which is the whole reason it fails instead of skipping.
        '            bound = _DERIVED.findall(line)',
        '            bound = _DERIVED.findall(line) or '
        '[(n, "lines", "README.md", "") for n in re.findall(r"\\b(\\d+)\\b", line)]',
        PYTEST + [str(ROOT / "apps/api/tests/test_drift.py")],
    ),
    Mutation(
        "drift-skips-a-marker-that-binds-to-nothing",
        "16 Oct: a derived marker binds to the nearest number on its own line, "
        "so a paragraph reflow that leaves the figure one line up makes it "
        "inert. Three markers in docs/SUBMISSION.md had been in that state "
        "since they were written — two of them stale, at 12 mutations against "
        "19 and 14 decision records against 15 — and this gate called the "
        "document clean every time. A guard that quietly stops applying is "
        "worse than no guard, because the summary still reassures.",
        "scripts/check-drift.py",
        "            if _MARKER.search(line) and not bound:",
        "            if False:",
        PYTEST + [str(ROOT / "apps/api/tests/test_drift.py")],
    ),
    Mutation(
        "drift-ignores-planned",
        "23 Sep: a tree that calls shipped work planned tells a reader that work "
        "remains which does not. The 16 Sep pass fixed the other direction and "
        "left this one, in the same document.",
        "scripts/check-drift.py",
        "if planned and exists:",
        "if planned and not exists:",
        PYTEST + [str(ROOT / "apps/api/tests/test_drift.py")],
    ),
    Mutation(
        "push-gate-skips-on-any-deletion",
        "23 Sep: the cheap reading of a pre-push payload — any all-zero hash "
        "means there is nothing to check — lets a red commit through behind a "
        "branch deletion in the same push.",
        ".githooks/pre-push",
        "        *[!0]*) only_deletions=false ;;",
        "        *[!0]*) : ;;",
        PYTEST + [str(ROOT / "apps/api/tests/test_push_gate.py")],
    ),
    Mutation(
        "report-exemption-wider-than-its-name",
        "12 Oct: the push gate skips the suites for a push that carries only a "
        "machine-session report, because none of them says anything about "
        "prose. A path check that stops refusing anything else turns "
        "docs/operations/reports/ into the way to push code unchecked — which "
        "is worse than the --no-verify habit the exemption exists to avoid.",
        ".githooks/pre-push",
        '            "${REPORTS_DIR}"*) ;;\n            *) return 1 ;;',
        '            "${REPORTS_DIR}"*) ;;\n            *) ;;',
        PYTEST + [str(ROOT / "apps/api/tests/test_push_gate.py")],
    ),
    Mutation(
        "score-forgets-its-generator",
        "10 Oct: eval_results.model_call_id existed from the first migration and "
        "the INSERT never named it, so the curve could not refuse a week 1 "
        "generated locally against a week 8 generated in the cloud. Writing the "
        "column as NULL is the silent version of the same defect: it reads as "
        "populated and the guard that reads it reads as holding.",
        "apps/api/secondshift/evals/runner.py",
        "json.dumps(judgement.scores), model_call_id,",
        "json.dumps(judgement.scores), None,",
        PYTEST + [str(ROOT / "apps/api/tests/test_evals.py")],
    ),
    Mutation(
        "curve-compares-across-models",
        "10 Oct: the curve refused six ways and none of them was the model "
        "changing between the two runs — the one difference the shortest path to "
        "a week-8 number actually introduces, reported as the brain learning.",
        "apps/api/secondshift/evals/runner.py",
        "if earlier.generators != later.generators:",
        "if False:",
        PYTEST + [str(ROOT / "apps/api/tests/test_evals.py")],
    ),
    Mutation(
        "judge-reads-a-truncated-judgement",
        "10 Oct: JSON cut off at a token limit still parses as a smaller valid "
        "object, so a judgement missing two dimensions scores on the rest — a "
        "wrong number that reads like a right one. The first real night lost "
        "three stages to the same shape of partial output read as whole.",
        "apps/api/secondshift/evals/judge.py",
        "if completion.finish_reason != STOPPED_CLEANLY:",
        "if False:",
        PYTEST + [str(ROOT / "apps/api/tests/test_evals.py")],
    ),
    Mutation(
        "curve-compares-across-prompts",
        "10 Oct: generating eval answers through the product's agent path put "
        "the generator hole back one layer up. A role prompt is versioned and "
        "eval_runs pins no prompt, so a prompt replaced between week 1 and "
        "week 8 moves the scores for a reason that is not memory. distiller was "
        "already at v2 when this was written.",
        "apps/api/secondshift/evals/runner.py",
        "if earlier.prompt_versions != later.prompt_versions:",
        "if False:",
        PYTEST + [str(ROOT / "apps/api/tests/test_evals.py")],
    ),
    Mutation(
        "a-deployment-scores-the-other-kind-of-run",
        "10 Oct: the is_synthetic flag marks results and the exclusion filters "
        "runs — two tables. So a judge deployment scoring a run recorded as real "
        "writes synthetic results under a real run, and summarize reads them as "
        "that run's scores because it filters results by nothing. The 19 Sep "
        "exclusion protects whole runs and never sees this.",
        "apps/api/secondshift/evals/runner.py",
        "if bool(recorded[\"is_synthetic\"]) != self._is_synthetic:",
        "if False:",
        PYTEST + [str(ROOT / "apps/api/tests/test_evals.py")],
    ),
    Mutation(
        "judge-reads-the-first-object-not-the-last",
        "11 Oct: the real checkpoint shows its work, so a judgement is preceded "
        "by deliberation that can contain braces and can contain a drafted set "
        "of scores the model then reconsiders. Taking the first object records "
        "the number it talked itself out of, or parses `{interrogation}` out of "
        "a sentence about the rubric.",
        "apps/api/secondshift/evals/judge.py",
        "                if depth == 0 and started is not None:",
        "                if depth == 0 and started is not None and not found:",
        PYTEST + [str(ROOT / "apps/api/tests/test_evals.py")],
    ),
    Mutation(
        "one-bad-trailing-object-burns-the-run",
        "16 Oct: three samples were refused because the last object balanced "
        "and did not parse. A refused sample burns the whole run — "
        "`eval_results` is unique per sample and `score` regenerates rather "
        "than tops up — so for the week-1 baseline that is unrecoverable. "
        "Reading only the last object reintroduces it.",
        "apps/api/secondshift/evals/judge.py",
        "        for candidate in reversed(candidates):",
        "        for candidate in candidates[-1:]:",
        PYTEST + [str(ROOT / "apps/api/tests/test_evals.py")],
    ),
    Mutation(
        "the-ask-shows-an-object-to-copy",
        "16 Oct: the instruction carried a balanced `{...}` whose first value "
        "was `<1-5>`, so a model echoing it produced an object that balanced "
        "and did not parse. json.loads failed at char 29 on all three, which "
        "is exactly that `<`. A template a model can copy is a template it "
        "can copy instead of answering.",
        "apps/api/secondshift/evals/judge.py",
        "Every dimension is required. Do not restate these instructions.",
        'Every dimension is required. Reply like {{"scores": {{"voice": <1-5>}}}}.',
        PYTEST + [str(ROOT / "apps/api/tests/test_evals.py")],
    ),
    Mutation(
        "the-judge-version-omits-the-ask",
        "16 Oct: `eval_runs` pinned the judge's model and version but not its "
        "instruction, leaving the one input to the measurement that could "
        "change without the comparison noticing. Two runs either side of an "
        "edit to the ask pass all ten of the curve's refusals while having "
        "been scored by different instruments.",
        "apps/api/secondshift/evals/judge.py",
        '        self.version = f"{version}+ask.{ask_sha()}"',
        "        self.version = version",
        PYTEST + [str(ROOT / "apps/api/tests/test_evals.py")],
    ),
]


def run(mutation: Mutation) -> bool:
    path = ROOT / mutation.path
    original = path.read_bytes()
    text = original.decode()
    found = text.count(mutation.before)
    if found != 1:
        print(f"FAIL  {mutation.name}: its target appears {found} times in "
              f"{mutation.path} — the code moved; update the mutation")
        return False
    started = time.monotonic()
    try:
        path.write_text(text.replace(mutation.before, mutation.after, 1))
        result = subprocess.run(mutation.gate, cwd=ROOT, capture_output=True, text=True)
    finally:
        path.write_bytes(original)
    elapsed = time.monotonic() - started
    if result.returncode == 0:
        print(f"FAIL  {mutation.name}: the gate stayed green ({elapsed:.1f}s)\n      {mutation.why}")
        return False
    print(f"ok    {mutation.name}: caught ({elapsed:.1f}s)")
    return True


def main(names: list[str]) -> int:
    selected = [m for m in MUTATIONS if not names or m.name in names]
    unknown = set(names) - {m.name for m in MUTATIONS}
    if unknown:
        print(f"unknown mutation(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2
    results = [run(m) for m in selected]
    missed = results.count(False)
    print(f"{len(results) - missed} of {len(results)} mutations caught")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
