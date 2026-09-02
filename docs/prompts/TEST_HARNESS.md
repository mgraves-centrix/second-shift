# Test harness prompt

Paste as the first message of a fresh session. Entirely local — no Spark, no
tailnet, no credentials.

**Independent of everything. Owns files nothing else touches, so it can run
alongside any other session.**

---

Build the test harness. Read `openspec/constitution.md`, `CLAUDE.md`, and
`docs/prompts/OVERNIGHT.md` first; they are the rules, not background.

## Why this one

**There is no CI.** No `.github`, no workflow, nothing. Every gate in this
project is run by hand, in a remembered order, by whoever is at the keyboard. On
2 Sep that meant six commands typed before and after every capability, and the
only reason nothing slipped is that nothing was forgotten yet.

The suite is real — 302 Python tests, 25 web tests — but its coverage of the
*wrong* things is unmeasured, and one concrete failure is on the record: on 2 Sep
a test asserting lanes-are-recorded-lanes passed against an implementation that
computed lanes by joining, because every lane in the fixture happened to have one
event with an invocation. It was caught by deliberately breaking the code, not by
the suite. **That is the gap this capability closes.**

There is also no end-to-end test of anything. The scrubber was verified by a
throwaway Playwright script that lives in a scratch directory and will not
survive this session.

## What already exists — do not invent any of it

- `apps/api/tests/` — 302 tests, pytest, `filterwarnings = ["error"]` in
  `pyproject.toml`, which is why an unclosed sqlite connection is a failure
  rather than a warning. Fixtures in `conftest.py` include a stub vLLM server on
  a real socket.
- `apps/web/tests/` — 25 tests, `node --test 'tests/*.test.ts'`, no jsdom and no
  component runner. Node runs TypeScript directly.
- `scripts/check-no-environment.sh` — scans **tracked and untracked** files for
  private addresses, tailnet names, home paths. It gained `--untracked` after a
  new file passed the check right up until the moment it was added.
- `scripts/check-american-english.sh`.
- `openspec validate --strict`, per change and per spec.
- `apps/api/tests/test_deploy_guards.py` and `test_deploy_units.py` — the deploy
  script is exercised with `ssh` and `npm` stubbed on PATH, and the systemd units
  are parsed and checked against `config/models.toml`. That pattern works; extend
  it rather than inventing a second one.
- Playwright 1.56 and a Chromium at `/opt/pw-browsers` are available in the web
  session environment. `PLAYWRIGHT_BROWSERS_PATH` is set; never run
  `playwright install`.

## The open decision

**What CI runs, given the deadline and a solo developer.**

The full gate set takes about ninety seconds locally. On every push that is
cheap; the question is what happens when it is not — the e2e suite needs a
browser and a seeded database, and a five-minute CI on a solo project is a five
minute wait before every merge, sixty days from a deadline.

**Do not decide this by preference.** Measure the current gate set end to end,
then measure it with a browser-driven e2e added, and propose the split with both
numbers. If the answer is "everything on every push," say so with the timing that
justifies it.

The second open thing: **mutation testing, or a discipline?** The lanes defect
argues for something systematic. A full mutation-testing tool over 302 tests is
slow and noisy. A convention — every gate test must be shown to fail once — is
free but unenforceable. Propose one, with the reasoning.

## What good looks like

- **One command runs every gate**, in the right order, and exits non-zero on the
  first failure. Nobody should have to remember six commands ever again.
- CI runs that same command. Not a parallel reimplementation that can drift from
  it — the local script and the workflow must not be two sources of truth.
- An **end-to-end test that survives the session**: seed a night, start the API,
  drive a real browser, assert the scrubber renders and scrubs. The throwaway
  script proved it is possible; make it a committed test.
- The e2e is **hermetic** — its own database, its own port, no dependence on the
  Spark, no network beyond localhost.
- A test that asserts the suite can fail: at least one gate has a documented
  mutation and a check that the mutation is caught.
- The deploy guard and unit tests keep passing without a real host, as they do
  today.

## Scope — what NOT to build

- **No coverage percentage gate.** A number that goes up by testing getters is
  worse than no number. If you report coverage, report what is uncovered and
  interesting.
- **No new test framework.** pytest and `node --test`. Adding a third is a tax on
  every future session.
- **No jsdom.** The web tests are pure functions by design; the rendering
  assertions belong in the browser-driven test.
- **No CI that deploys.** Nothing in this repository should be able to touch the
  always-on machine automatically.
- **No secrets in CI.** Nothing here needs a credential, and it must stay that
  way — the e2e runs against a stub reasoner, never Token Factory.
- **No flaky-test retry.** A retry is how a real failure becomes background noise.

## Constitution hooks

- **Principle 7.** The suite must keep proving that telemetry is not optional:
  the tests that assert a model call writes a row, and that a failed call writes
  a failure, are load-bearing. Do not let a refactor make them conditional.
- **Principle 2.** Keep the airlock tests in the gate set and run them first —
  they are the fastest and the most important. A build that fails on a privacy
  test should not wait behind a browser download.
- **Principle 5.** The gate script runs identically on a laptop, in CI and on the
  Spark. Never `uv run` on the Spark; it re-resolves the environment to x86_64
  and destroys it.

## The loop

```bash
git status --short && openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q          # 302 pass today
npm --prefix apps/web run test && npm --prefix apps/web run typecheck
scripts/check-no-environment.sh && scripts/check-american-english.sh
```

All green before starting. That command list is the thing you are replacing;
keep it working until the replacement is proven.

## Verification — the harness must be shown to catch things

A test harness that has never caught anything is a hypothesis.

- **Break something on purpose and watch CI go red.** Revert a guard, push to a
  branch, confirm the failure, revert. Paste the failing run.
- Re-run the four mutations that were checked by hand on 2 Sep — frame from the
  last start, no minimum bar width, lanes built by joining, stages dropped — and
  confirm the gate catches each. **The third one initially did not.**
- The e2e **must be able to fail**: break the scrubber's playhead transform and
  watch the browser test go red. That exact defect shipped through three passing
  tests on 2 Sep because they read the ARIA value rather than the rendering.
- The e2e fails when the API is not running, with a message that says so rather
  than a timeout.
- The gate script exits non-zero on the first failure, and the exit code is the
  failing gate's.
- Run the whole thing on a clean clone with no `.venv`, and confirm the
  bootstrap is documented and works. A gate that only runs on a machine that
  already ran it is not a gate.

## Quality bar

The code is the submission. Judges read this repository.

**Never ship:** a test that passes with the implementation deleted; a retry that
hides a flake; a CI workflow that duplicates the gate script instead of calling
it; a mock of the thing under test; a broad `except` that makes a gate green; a
sleep where a wait-for belongs.

**Always:** match the surrounding idiom; prefer the boring construction; make
failures name what broke and where; keep the harness dependency-light. American
English. No hostnames, addresses, usernames or home paths in tracked files —
this capability writes CI configuration, which is exactly where they leak.

## Hard stops

Stop, record the question with your recommendation, and move on:

- A `[NEEDS CLARIFICATION]` marker. Do not answer your own.
- A constitution violation. Blocking, not advisory.
- Anything in `NOT_BUILDING.md`.
- **Credentials.** CI secrets, tokens, deploy keys — none of them, and a
  workflow that would need one is the wrong workflow.
- Rewriting published history or force-pushing.

## Report

1. The two timings, and the CI split you proposed from them.
2. The mutation you pushed to prove CI catches things, with the red run pasted.
3. Which of the four 2 Sep mutations the gate set catches, and any it does not.
4. What shipped, with test counts.
5. Anything blocked, with your recommendation.
6. What you would do next, and why that rather than the alternative.
