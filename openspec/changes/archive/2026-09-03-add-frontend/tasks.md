# Tasks — `frontend`

## 1. The token system

- [x] 1.1 `app/tokens.css` — every color property, declared once.
- [x] 1.2 Move the scrubber's six in. **Do not touch its render path**; moving a
      declaration does not change the selectors that read it.
- [x] 1.3 A test asserting no component stylesheet declares a color of its own,
      so the next surface cannot repeat `--severe`.

## 2. Scoping capture, without changing it

- [x] 2.1 Capture's element styles move to `app/capture.module.css`.
- [x] 2.2 `globals.css` keeps the reset, the type ramp and the token import.
- [x] 2.3 **Screenshot capture before and after and compare.** This is the risky
      edit in the change: identical rendering is the only acceptable result.

## 3. The shells

- [x] 3.1 `components/shell/` — a nav for desktop surfaces.
- [x] 3.2 A footer for capture, **below** the capture control.
- [x] 3.3 The night surface gets the nav; capture gets the footer.
- [x] 3.4 Assert the policy options sit no lower than they do today.

## 4. The demo label

- [x] 4.1 A component reading the served capability report.
- [x] 4.2 Renders on `cloud`, absent otherwise. No build flag.

## 5. Verification

- [x] 5.1 Capture measured no busier: policy visibility at keyboard-up
      viewports is unchanged from today's numbers.
- [x] 5.2 320px and 1920px, no horizontal overflow.
- [x] 5.3 Keyboard reachable; focus visible; the scrubber's slider role intact.
- [x] 5.4 `npm run build` — static export still succeeds.
- [x] 5.5 Full Python suite, web tests, typecheck, both guards.
- [x] 5.6 `openspec validate --strict`.

## 6. Recorded, not built

- [x] 6.1 **Capture hides the privacy choice with the keyboard up, and it does
      that today with no nav involved** — 0% visible at 390×300 on the shipped
      page, whole from 390px up. It bites on small phones (an iPhone SE with a
      keyboard leaves roughly 308px), not on every phone.
      The fix is to put the policy choice above the textarea so the thing that
      falls off the bottom is never the privacy decision. That changes the shape
      of the 3am screen, so it is the subject's call and not a refactor's.
- [x] 6.2 **`app/morning/`** — this unblocks it; `MORNING_INTERVIEW.md` owns it.
- [x] 6.3 **Charts sharing the scrubber's time axis.** The component was built
      for three callers and this makes the second possible, not real. No chart
      surface exists to brush against yet.


## Mutations run

| Mutation | Result |
|---|---|
| A nav appears on capture | `capture does not import the nav` red |
| The footer moves above the capture button | `capture renders its links after the capture control` red |
| The scrubber declares its own color again | `no other stylesheet declares a color token` and `the scrubber's layout values stay with the scrubber` both red |

## Two defects in this change's own work

- **The measurement in the first proposal was taken against a mock.** It used
  the real stylesheet but invented policy text, and reported 81% / 10% at
  390×390. The built page is more compact and the real numbers are different —
  0% versus 79% at 390×350, 100% versus 71% at 390×390. The conclusion did not
  change and got sharper, but a measurement against a stand-in is not a
  measurement of the thing, and the proposal now carries the real table with
  that correction written into it.
- **The demo label shipped on capture and not on the night surface.** The shell
  took it as a prop and the night page rendered `<Nav />` without one, so the
  screen a judge is most likely to open was the one not saying it was a demo —
  a principle 5 requirement, missed by a forgotten argument. The shell now
  fetches the capability report itself, and a test asserts it takes no such
  prop, because a label every caller has to remember is a label that goes
  missing.

One test was also **overbroad and had to be narrowed**: it forbade `process.env`
anywhere in the shell, which failed the moment the shell needed to know where
the API is — and would have pushed the label back to the prop that had just
caused the bug. It now forbids a flag that *decides* the label and requires the
served report to be read.

## Measured, not asserted

Capture's privacy choice is unchanged by this capability:

```
                shipped before   after this change
  390x350             79%              79%
  390x390            100%             100%
```

The footer costs nothing above the fold, which is what it was placed below the
button for. No horizontal overflow at 320px, 390px or 1920px on either surface,
and both carry links to every built surface.


## The follow-up audit, and three more findings

Run after archiving, the same way the 3 Sep audit was: for each public symbol in
the new code, does anything outside its own module reference it?

- **`DemoLabel` was exported and imported by nothing.** Used only by `Nav` and
  `Footer` in its own file. Un-exported — a symbol nothing imports is surface
  with no consumer.
- **`SURFACES` was exported and only asserted by reading the file's text.** The
  test grepped `Shell.tsx` for `href: "/night/"`, which passes whatever the
  symbol is called and fails to notice a rename. Trying to import it properly
  found the real constraint: `node --test` strips types but does not transform
  JSX, so nothing in a `.tsx` file can be imported by a test at all. The list is
  data, so it moved to `lib/surfaces.ts` — which also makes it the extension
  point the morning session was told to use, one line rather than an edit inside
  a component.
- **A test narrowed after it overreached.** `no build-time flag governs the
  label` forbade `process.env` anywhere in the shell, and failed the moment the
  shell needed to know where the API is. It now forbids a flag that *decides*
  the label and requires the served report to be read — and a second test
  asserts the shell takes no `demo` prop, which is the defect that caused the
  night surface to ship unlabeled.

A mutation was run on the moved list: dropping the trailing slash from
`/night/` turns two tests red, which under `trailingSlash: true` and a static
export is a link the file server cannot follow.
