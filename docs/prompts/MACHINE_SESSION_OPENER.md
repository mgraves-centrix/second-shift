You are driving the always-on machine over SSH from this laptop. Every command
executes there; nothing but the web build runs locally. The database, the brain
repository and the model all live on that machine.

Read these first, in this order. They are the rules, not background.

- `openspec/constitution.md` and `CLAUDE.md`
- `docs/operations/reports/2026-10-16-machine-session.md` — the only account of
  what that machine actually does, written by the session that last drove it
- `docs/prompts/ENDGAME.md` — your step list. Start at step 0
- `docs/operations/RECOVERY.md`, and `docs/SPEC_ROADMAP.md`'s *What a machine
  session owes*

Work ENDGAME.md's steps 0 through 7 in order and stop at the first one that
fails. The order's reasons are in the file; the one worth repeating here is that
**step 2's refusal rate decides whether step 4 is safe**, and step 4 can destroy
the one artifact in this project that cannot be remade — the week-1 eval
baseline, `01M1FYFECEXC5ZJEWHNP7WZMXB`.

Write `<spark>` for the machine and `~/...` for home paths in anything you
commit. This repository is public, and `scripts/check-no-environment.sh`
enforces it by position in an `ssh` invocation rather than by spelling, because
the machine's short name is also this project's compute-profile name.

Three things in this session touch real data for the first time, so check each
rather than assuming it: `model_call_payloads` holding rows,
`eval_results.output_path` being populated, and a backup carrying the payload
tree. Report each as a count and a path, never as content.

Hard stops. Record the question with your recommendation, and move on:

- **Never read, print, copy or echo a credential.**
  `~/.config/second-shift/secrets.env` and `~/.config/second-shift/keys/` are
  off limits. Use one that is already configured.
- **Never `uv run` on that machine.** It re-resolves the environment to x86_64
  and destroys it. Use `python -m venv` and `pip` with pinned constraints.
- **Never loosen a refusal to get a number** — not the judge's parse, not the
  curve's ten refusals, not the airlock's policy constant. Each one exists
  because the alternative is a wrong number that reads like a right one.
- **No new capability, and no stub executor.** A stub writing plausible job rows
  is indistinguishable from the fan-out that is the whole evidence for the
  Nebius claim.
- A constitution violation, a `[NEEDS CLARIFICATION]` marker, or anything in
  `NOT_BUILDING.md`.

Hand the result back by pushing a report, not by pasting it.
`docs/operations/reports/README.md` is the contract: one file, on a
`reports/YYYY-MM-DD-what-it-was` branch, placeholders always, and **say what did
not work** — a refusal, a missing file, an unreachable reasoner and a step not
attempted are all findings. A push touching only that directory runs the two
source checks rather than the suites, so this needs git and bash and not a web
toolchain. Do not reach for `--no-verify`; if a push is refused it will be a
hostname or a home path.

ENDGAME.md's *Report* section says what the report must answer. The number that
matters most is the judge's refusal rate against the real checkpoint, as a
fraction — that is what the last session stopped over.
