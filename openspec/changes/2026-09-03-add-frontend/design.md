# Design — `frontend`

## Decision 1 — tokens in one file, imported once, consumed everywhere

`app/tokens.css`, imported by `globals.css`. The scrubber's six properties move
into it; `scrubber.module.css` keeps its own layout values and stops declaring
color.

**Alternative considered:** leave the scrubber's tokens where they are and add a
convention. Rejected — the convention is what already failed. `--severe` exists
because the scrubber needed a severity color and had nowhere to put it, so the
next surface will do the same thing for the same reason.

**The constraint that shapes this:** the scrubber's render path is measured at
0.1ms per steady frame and must not be touched. Moving a custom property
declaration does not touch it — the selectors that read the property are
unchanged.

## Decision 2 — capture's element styles get scoped, and the proof is a rendering

`globals.css` currently styles `button`, `textarea`, `main`, `h1`, `fieldset`
and `legend` globally. Those move to a CSS module that capture imports.

This is the risky edit in the whole change, because capture is live. So the
verification is not "the tests pass" — it is **a screenshot of capture before
and after, compared pixel by pixel**, at the viewports that matter. A refactor
that renders identically is a refactor that worked; anything else is a
regression on the one screen that must not regress.

**Alternative considered:** leave the element selectors and add `:where()` to
lower their specificity. Rejected — it keeps capture's layout global, so the
next surface still has to opt out of `max-width: 34rem` rather than opt in.

## Decision 3 — two shells, and the asymmetry is the point

Capture: no chrome above the content, a footer below the button.
Night and morning: a real nav.

They share `tokens.css`, one type ramp and one spacing scale, which is where the
coherence lives. A nav bar on capture would buy visual consistency at the cost
of the privacy choice, and the measurement in the proposal is what settles that
trade rather than an argument about design systems.

**Alternative considered:** a nav that collapses to an icon on narrow viewports.
Rejected — it still occupies the vertical space, which is the axis that is
scarce when a keyboard is up, and it adds an interaction to the screen the
constitution wants frictionless.

**Alternative considered:** no navigation from capture at all, and a separate
index page. Rejected — `/` is capture and moving it would break an installed
PWA's start URL, which is the one thing on a home screen nobody can fix remotely.

## Decision 4 — the demo label is driven by data, not by a build flag

The API already serves `/capabilities` with the resolved profile. The label
component reads it and renders when the profile is `cloud`.

**Alternative considered:** `NEXT_PUBLIC_DEMO=1` at build time. Rejected — that
is two builds, and principle 5 says one codebase separated only by compute
profile. A build flag is the fork the principle exists to prevent, and it would
also mean the judge instance and the personal instance are not the same artifact.

## Decision 5 — static export stays intact

`next.config.mjs` sets `output: "export"`. Every route added is static; nothing
introduces a dynamic segment needing `generateStaticParams` over ids unknown at
build time.

That is not a preference either: a second running server on the always-on
machine is a second thing that can be down at 2am when an idea arrives, and the
API serves the PWA as files precisely so that cannot happen.
