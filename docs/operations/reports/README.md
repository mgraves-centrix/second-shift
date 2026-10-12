# Machine-session reports

What a session on the always-on machine found, written where it can be read
without anybody scrolling a transcript.

## Why this exists

A cloud session cannot reach that machine, and a session that can — on the
machine, or on the laptop over SSH — runs somewhere its findings are invisible
to whoever asked for them. Relaying a report by hand works once. It does not
work for a sequence of sessions, and the endgame is a sequence.

So a report is a commit. The session writes one file here, pushes it to a
branch, and anybody who can fetch the repository can read what happened,
including a session that was not there.

## The contract

- **One file per session**, named `YYYY-MM-DD-what-it-was.md`.
- **A branch, not the trunk**: `reports/YYYY-MM-DD-what-it-was`. A report is
  evidence from a session nobody watched, so it is read before it joins `main`.
- **Say what did not work.** A refusal, a missing file, an unreachable reasoner
  and a step not attempted are all findings. A guess presented as a result is
  worse than no result, and this directory is cited by documents that claim
  things.
- **Placeholders, always.** `<spark>` for the machine, `<host>` for anything
  else, `~/...` or `$HOME` for a home directory. This repository is public.

## What the push gate does on this path

`.githooks/pre-push` runs the two source checks — no environment details,
American English — and **not** the suites, the build, the browser test or the
mutations, because none of them says anything about prose. A session on the
machine therefore needs git and bash to hand back a result, not a web
toolchain.

That exemption is scoped by path and refuses the moment a push touches anything
outside this directory. It exists so nobody reaches for `git push --no-verify`,
which would defeat the mechanism that stopped two red commits in three days.

**The check it keeps is the one that matters here.** A hostname in a report is a
hostname in a public repository, and the machine's short name is also this
project's compute-profile name — so no pattern can catch it by spelling, and
`check-no-environment.sh` catches it by position in an `ssh` invocation instead.

## What a report is not

- **Not a decision record.** If a session's findings settle an architectural
  question, that is an ADR in `docs/decisions/`, and the report is what it
  cites.
- **Not a task list.** Owed work belongs in `docs/SPEC_ROADMAP.md`, where
  somebody deciding what to do next will look.
- **Never payload text.** No prompt or completion text, and nothing about the
  subject's actual captured ideas. `model_call_payloads` exists so that content
  stays on that machine; a report quotes the *shape* of a completion, not its
  contents.
