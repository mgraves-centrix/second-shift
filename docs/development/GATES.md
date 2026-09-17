# Gates

One command runs every gate, in order, and stops at the first failure with that
gate's exit code:

```bash
python3 scripts/gate.py
```

CI runs the same file (`.github/workflows/gate.yml`). It installs tools and calls
the script; it never restates the gates.

## The gates, in order

| Gate | What it proves |
|---|---|
| airlock | Profile and policy refusals, redaction, and the research egress path. First because they are the fastest and the most important. |
| no environment details | No private address, tailnet name or home path in a tracked or new file. The repository is public. |
| American English | No British spellings in anything authored here. |
| specs | `openspec validate --all --strict`. |
| api | The full orchestrator suite. Warnings are errors. |
| web unit | Pure-function tests under `node --test`. |
| web types | `tsc --noEmit`. |
| web build | The static export the orchestrator serves. |
| browser | A seeded night, a real orchestrator on a free port, and the installed Chrome. Asserts rendering from geometry, never from ARIA. |
| mutations | Reintroduces defects this project has shipped and requires the gate that should catch each to fail. |

Measured on 17 Sep: 46 seconds end to end on a laptop, of which the orchestrator
suite is 29. The browser test adds 2 and the mutations 8. Everything runs on every
push; there is no fast path, because at this size one would save less than a
minute and cost a second definition of "passing."

## Bootstrap from a clean clone

Needs Python 3.12 or later, Node 24, and Google Chrome.

```bash
python3 -m venv apps/api/.venv
apps/api/.venv/bin/pip install -c apps/api/constraints.txt -e "apps/api[dev]" -e packages/seed
npm --prefix apps/web ci
npm install --global @fission-ai/openspec@1.11.0
python3 scripts/gate.py
```

Never `uv run` on the always-on machine; it re-resolves the environment to
x86_64 and destroys it.

`GATE_PYTHON` points the gate at a different interpreter, and `GATE_CHROME` the
browser test at a Chrome binary other than the installed one.

## Adding a mutation

When a defect ships, add it to `scripts/check-mutations.py`: the exact text that
fixes it, the text that reintroduces it, and the one gate that must go red. The
runner fails if the text no longer appears exactly once, so a mutation cannot
silently stop applying when the code moves.

That is the discipline instead of a mutation-testing tool: a full tool over
seven hundred tests is slow and mostly reports mutants nobody would write. A
convention that every gate test "was shown to fail once" is free and
unenforceable. A short list of defects that actually happened, re-run on every
push, is neither.
