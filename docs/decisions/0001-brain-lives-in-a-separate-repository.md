# 0001 — The brain lives in a separate repository

**Status:** accepted · **Date:** 2026-08-27

## Context

The brain — skills, style guide, failure ledger, profile — is plaintext markdown
under git, and its diff between week 1 and week 8 is the submission's
centerpiece. The night pipeline commits to it after every stage, so it will
accumulate hundreds of automated commits over nine weeks.

The code repository's commit history is separately load-bearing: it is the
evidence the project was built during the hackathon window.

## Decision

The brain is its own git repository in a sibling directory (`../second-shift-brain/`),
not a subdirectory and not a submodule. The code repo ignores `brain/`.

## Consequences

- Code history stays readable as evidence. Automated commits do not bury it.
- `git -C ../second-shift-brain diff <week1-sha>..<week8-sha>` is the demo, and
  it is clean.
- `runs.brain_sha` and `eval_runs.brain_sha` pin brain state per run, so the two
  histories stay correlatable without being coupled.
- Cost: two clones to set up, and the brain repo needs its own backup. Accepted.
- Rejected: submodule. It gets both properties at the price of constant
  submodule friction during a nine-week solo sprint.
