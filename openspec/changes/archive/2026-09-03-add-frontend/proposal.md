# Add `frontend` — one token system, and a shell that does not cost capture

## Scale classification

**L3 — Epic.** It establishes the token and layout contract every surface
consumes, unblocks `morning-interview`'s screen (which shipped its server half
deliberately without one), and Design is one of four equally weighted judging
criteria. Design doc included.

## Why

Two surfaces exist and **nothing links them** — verified: no `href` or `Link`
between `/` and `/night/` anywhere in `app/`. A judge who opens the root sees a
textarea and has to know a URL.

And the tokens are drifting, exactly as claimed: **8** custom properties in
`app/globals.css`, **6** more inside `components/scrubber/scrubber.module.css`
including `--severe`, a severity color the capture surface knows nothing about.

**A second drift underneath it, found by reading the file rather than the
prompt.** `globals.css` styles bare element selectors — `main`, `h1`, `button`,
`textarea`, `fieldset`, `legend` — so `button { width: 100% }` and
`main { max-width: 34rem }` are capture's layout applied to every surface that
will ever exist. That is worse than a duplicated color: a new surface inherits
capture's shape whether it wants it or not, and the scrubber already works
around it. Fixing it must not change a pixel of the screen taking real ideas.

## The open decision — one shell, or two that share a system

**Decided by building both and measuring, not by preference.** The capture
markup and the real stylesheet were rendered at phone viewports, with and
without a nav bar, at the keyboard-up heights that are the state that matters.

The measurement is what `local-only` — the privacy choice — does as the viewport
shrinks. **Measured against the built page**, served with a real capability
report, with the shipped nav inserted above the content:

| viewport | shipped (no nav) | with a nav bar |
|---|---|---|
| 390×300 | 0% visible | 0% visible |
| 390×350 | **79% visible** | **0% visible** |
| 390×390 | **100%** | **71%** |
| 390×420 | 100% | 100% |
| 390×450 | 100% | 100% |

**The nav costs capture the privacy choice in the band that matters.** At 350px
of remaining viewport it is the difference between seeing `local-only` and not
seeing it at all; at 390px, between whole and clipped. The default is
`cloud-assisted`, the option that sends the idea off the machine, so a person
who does not scroll takes the wider policy by omission. That is principle 2
territory, not a layout preference.

> **The first version of this table was measured against a mock**, built from
> the same stylesheet but with invented policy text, and it reported 81% / 10%
> at 390×390. The real page is more compact and the real numbers are different —
> and sharper. The conclusion did not change, but the figures did, and a
> measurement taken against a stand-in is not a measurement of the thing.

**So: two shells that share one system.** Capture gets no chrome above the
content. The desktop surfaces — the night, and the morning when it lands — get a
real nav, because they have 1,200 pixels and no keyboard problem. Coherence
comes from the token system and one type ramp, not from a bar on the 3am screen.

Capture still reaches the other surfaces: a footer **below** the capture button,
which costs nothing above the fold because nobody needs it at 3am and a judge
scrolling one screen finds it immediately.

## A second finding, and it is not this capability's to fix

**Capture already hides the privacy choice with the keyboard up, with no nav
involved.** At 390×300 the `local-only` option is **0% visible** in the current
shipped screen. It is whole from 390px up, so this bites on small phones — an
iPhone SE with a keyboard leaves roughly 308px — rather than on every phone.

This was found while measuring something else and it is a real defect in a live
screen: the moment a person is deciding whether an idea leaves the machine is
exactly when the option to keep it home is off-screen.

**It is not fixed here, and that is deliberate.** The fix is to reorder capture
— the policy choice above the textarea, so the thing that falls off the bottom
is never the privacy decision — and that changes the shape of the screen a person
uses at 3am. The prompt is explicit that capture must be *no busier than today*
and that breaking it costs captures that cannot be recovered. **Recorded with a
recommendation for the subject to decide**, not changed unilaterally.

## What ships

- `app/tokens.css` — every custom property, in one file, imported once. The
  scrubber's six move into it; its render path is untouched.
- `globals.css` keeps only the reset and the type ramp. Capture's element styles
  move to `app/capture.module.css`, scoped, with the rendered result asserted
  identical.
- `components/shell/` — the nav for desktop surfaces, and a footer for capture.
- A root that reaches every surface without typing a URL.
- **The demo-label seam.** Principle 5 requires the judge instance to be labeled
  in-UI. The place it goes is built now, driven by the capability report the API
  already serves, so judge mode is a caller rather than a fork.

## Constitution compliance

| Principle | Outcome | Why |
|---|---|---|
| 1. Brain plaintext under git | **Not implicated** | No brain access. |
| 2. Privacy Airlock | **Constrains, and it decided the shell** | The policy choice must be visible where the decision is made. That measurement is why capture gets no nav. |
| 3. No empty mornings | **Constrains** | Surfaces render partial state; nothing shows an error in place of what exists. |
| 4. Text-first | **Constrains** | Every affordance is operable by typing and keyboard-reachable; the scrubber's slider role is the floor and is not regressed. |
| 5. One codebase, two deployments | **Constrains** | The demo label is a component driven by the served capability report, so judge mode is a caller and not a fork. |
| 6. Scope boundary | **Compliant** | Checked against both `NOT_BUILDING.md` tables. Capture shows a count, not a list with per-item controls — a surface that grew one would be task management. |
| 7. Telemetry from line one | **Not implicated** | The frontend reads; it opens no invocation and writes no row. |

No violations.

## Non-goals

- No component library, no CSS framework, no new dependency. Three today.
- No `app/morning/` — that is `MORNING_INTERVIEW.md`'s, now unblocked.
- No judge mode, no scrubber rewrite, no dark/light toggle, nothing that writes.
- **No reorder of capture.** See the second finding.
