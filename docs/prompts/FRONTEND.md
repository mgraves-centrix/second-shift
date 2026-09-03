# Frontend prompt

Paste as the first message of a fresh session. Entirely local — no Spark, no
tailnet, no credentials.

**Independent. Runs in parallel with `CONFIGURATION.md`, `AGENTS.md`,
`RETRIEVAL.md` and `TEST_HARNESS.md`. Must land before `MORNING_INTERVIEW.md`.**

> **It did not, and that is now the thing this unblocks.** `morning-interview`
> shipped its server half on 3 Sep — briefing, questions, answering, policy
> upgrade, all reachable at `GET /morning` and
> `POST /decisions/{id}/answer` — and deliberately shipped **no screen**,
> because this prompt says it must land first and the reason is the drift below.
> `app/morning/` is still `MORNING_INTERVIEW.md`'s to build; this makes it
> possible to build without making the drift worse.

---

Build the frontend shell and design system. Read `openspec/constitution.md`,
`CLAUDE.md`, and `docs/SPEC_ROADMAP.md` first; they are the rules, not
background.

## Why this one

**Design is one of four equally weighted judging criteria**, and it is graded as
"a complete, coherent product experience, not just a technical proof of concept."
Everything else in this project argues the system works. This is what makes it
look like one product rather than three demos in a trench coat.

> **✅ Shipped 3 Sep — `openspec/changes/archive/2026-09-03-add-frontend`.**
> Kept as the record of what was asked. Two things to carry forward:
>
> 1. **Its open decision was answered by measuring, and the answer was
>    asymmetric.** A nav bar on capture takes the `local-only` policy option
>    from 79% visible to 0% at 390×350. Capture gets links below its button;
>    the desktop surfaces get a nav.
> 2. **A finding it did not fix:** capture hides that policy option entirely at
>    390×300, on the shipped screen with no nav involved. The fix reorders the
>    3am screen, so it is the subject's call.

Right now there are two surfaces and **no way to get from one to the other.**
`/` is capture, `/night/` is the scrubber, and nothing links them — you have to
know the URL. A judge who opens the app sees a textarea.

The design tokens are already drifting. Eight custom properties live in
`app/globals.css` and six more were added inside
`components/scrubber/scrubber.module.css`, including a severity color the capture
surface knows nothing about. Two more surfaces are coming. Fix the system before
they land, not after.

## What already exists — do not invent any of it

- `app/page.tsx` — the capture PWA. **It is live and taking real ideas.** Four
  real entries. Breaking it costs captures that cannot be recovered.
- `app/night/page.tsx` and `components/scrubber/` — the night scrubber, built
  2 Sep. Incremental DOM, measured at 0.1ms per steady frame against a 16.7ms
  budget. It is the signature component and it is **built once, used three
  times**: the night view, judge mode's "run the night", and the shared time axis
  the trend charts brush against.
- `app/globals.css` — the palette: `--bg #0b0d10`, `--panel`, `--line`, `--text`,
  `--muted`, `--accent #7ef0a8`, `--warn`, `--disabled`. Dark by default, and
  that is not a preference — capture happens at 3am.
- **And the same file styles bare element selectors** — `main`, `h1`, `button`,
  `textarea`, `fieldset`, `legend`. `button { width: 100% }` and
  `main { max-width: 34rem }` are capture's layout, applied globally. That is a
  second drift underneath the token one and it is worse: a new surface inherits
  capture's styling whether it wants it or not, and the fix has to happen without
  changing a pixel of the screen that is taking real ideas.
- `next.config.mjs` sets `output: "export"` and `trailingSlash: true`, so the API
  serves the PWA as files. **A second running server on the Spark is a second
  thing that can be down at 2am.** Any route you add must survive static export;
  a dynamic segment needs `generateStaticParams` over ids unknown at build time.
- A PWA manifest, a service worker, and an icon. Capture works offline.
- Tests are `node --test` over plain TypeScript. There is no component test
  runner and no jsdom — 25 web tests today, all of them pure functions.

## The open decision

**One shell over both surfaces, or two shells that share a system?**

They pull in opposite directions and the tension is real:

- Capture is a phone surface. `globals.css` says it in a comment — *the capture
  screen must stay reachable with a keyboard open on a phone*. It is installed to
  a home screen, works offline, and is used one-handed in the dark.
- The scrubber needs 1,200 pixels to put a pixel on 22 seconds. It is a desktop
  surface and always will be.

A single shell with a nav bar risks putting chrome on the one screen that must
stay frictionless. Two shells risk exactly the incoherence the Design criterion
punishes.

**Do not decide this by preference.** Decide it by building the capture screen
both ways and looking at them on a phone viewport — with the on-screen keyboard
up, which is the state that actually matters. Report what you saw. If the nav
costs capture anything, capture wins; say so and design the coherence somewhere
that is not the 3am screen.

## What good looks like

- **One token system**, in one place, that every surface consumes. Adding a
  fourth surface should require no new colors.
- A judge who opens the root can reach every surface without typing a URL, and
  can tell what the product is within one screen.
- The capture screen is **no slower and no busier** than it is today. Measure it,
  do not assert it.
- Charts share the scrubber's time axis rather than reimplementing one. The
  component was built for three callers; make the second one real.
- It reads as deliberate at a glance — spacing on a scale, one type ramp, states
  that are visibly states. Default component-library styling is a scored loss.
- It works at 320px and at 1920px, and nobody has to be told which one it was
  designed for.
- Keyboard reachable throughout, and focus is visible. The scrubber already sets
  this bar with a real slider role; do not regress below it.

## Scope — what NOT to build

- **No component library.** No MUI, no Chakra, no shadcn install. The repository
  has three dependencies and that is a feature.
- **No CSS framework.** No Tailwind. CSS modules and custom properties, matching
  what is there.
- **No morning interview.** `MORNING_INTERVIEW.md` owns `app/morning/`.
- **No judge mode.** Same components, different caller, later.
- **No rewrite of the scrubber.** It is measured and it works. You may move its
  tokens into the system; do not touch its render path.
- **No dark/light toggle.** Dark, because 3am.
- **Nothing that writes.** No new mutation surface.

## Constitution hooks

- **Principle 4 governs the surfaces.** Every voice interaction has a working
  text equivalent that is not a degraded fallback. Any affordance you add for the
  interview must be operable by typing.
- **Principle 5.** One codebase, two deployments. The judge instance runs this
  same frontend on the `cloud` profile and must be **labeled in-UI as a demo** —
  build the place that label goes now, so judge mode is a caller and not a fork.
- **Principle 6.** A surface that grows a list of captured items with per-item
  controls has crossed into task management. Capture shows a *count* on purpose.

## The loop

```bash
git status --short && openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q          # 587 pass today
npm --prefix apps/web run test && npm --prefix apps/web run typecheck
npm --prefix apps/web run build                                # must still export
scripts/check-no-environment.sh && scripts/check-american-english.sh
```

All green before starting. Then propose, clarify, apply, verify, sync, archive.

To see it against real data:

```bash
apps/api/.venv/bin/python -m secondshift_seed --seed 42 --db /tmp/night.db
SECOND_SHIFT_DB=/tmp/night.db SECOND_SHIFT_PROFILE=cloud \
  apps/api/.venv/bin/uvicorn secondshift.api.main:app --port 8099
```

## Verification — a green suite cannot tell you it looks right

**Automated**, and these must be able to fail:

- The static export still builds, and every route is in it.
- Capture still posts an entry and still deduplicates a replay.
- No surface defines a color outside the token system — scan the CSS and assert
  it. That test is what stops the drift that already started.
- Tab order reaches every control on every surface; focus is visible.

**Visual — actually look at it.** Screenshot every surface at 390px and 1440px,
open the images, and read them. Report what you saw, not what you built. A
screenshot you did not open is not verification: on 2 Sep a playhead sat at the
left edge reporting the correct time through three passing tests, and only a
screenshot caught it.

**On a phone if you can.** The capture screen's requirement is a real device with
a real keyboard up.

## Quality bar

The code is the submission. Judges read this repository.

**Never ship:** hardcoded sample data standing in for the API; lorem text; `any`
in TypeScript; a `useEffect` that fetches without cleanup; a component that
re-renders a list on every pointer move; magic numbers for layout that should be
tokens; a color defined outside the system; a docstring restating the signature.

**Always:** read from the real API; match the existing idiom — read
`app/page.tsx` and `app/globals.css` first; keep the capture PWA working, it
takes real ideas. American English. No hostnames, addresses, usernames or home
paths in tracked files.

## Hard stops

Stop, record the question with your recommendation, and move on:

- A `[NEEDS CLARIFICATION]` marker. Do not answer your own.
- A constitution violation. Blocking, not advisory.
- Anything in `NOT_BUILDING.md`.
- Credentials, payment, account settings, or anything outward-facing.
- Rewriting published history or force-pushing.

**Capture is live.** Prove it still works after anything you change. If it breaks
and you cannot fix it in ten minutes, revert, verify, and stop.

## Report

1. The shell decision, with what you saw on a phone viewport with the keyboard up.
2. Screenshots of every surface at both widths, and **what you saw** — honestly.
   If it still looks like a technical demo, say so.
3. What shipped, with test counts.
4. What the capture screen costs now versus before, measured.
5. Anything blocked, with your recommendation.
6. What you would do next, and why that rather than the alternative.
