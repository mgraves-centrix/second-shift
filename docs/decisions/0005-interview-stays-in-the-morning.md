# 0005 — The interview stays in the morning

**Status:** accepted · **Date:** 2026-08-27

## Context

The product thesis is "it interrogates your idea *before* spending compute on
it." The loop as designed is capture → overnight run → morning interview, which
means night 1 spends full compute on an uninterrogated idea. The interview only
gates night 2 onward.

Alternatives considered:
- A 2–3 question micro-interview at capture time on local Nano, making the
  tagline literally true.
- A night stage 1 that produces questions only and gates the expensive stages.

## Decision

Keep the loop as originally specified. Morning interview only.

## Consequences

- Simplest loop; capture stays instant, with nothing between having an idea and
  it being recorded. Friction at capture is the one thing that would kill
  dogfooding.
- The thesis is directionally rather than literally true on the first night for
  any given idea. **The demo narration must address this before a judge asks
  it** — the honest framing is that the first night is exploratory and the
  interview is what makes every subsequent night cheaper and sharper, which the
  cost-per-accepted-artifact curve should show.
- Revisit only if the capture-time variant becomes free — i.e. if Nano latency
  turns out to be low enough to be invisible.
