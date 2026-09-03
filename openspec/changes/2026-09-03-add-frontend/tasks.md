# Tasks — `frontend`

## 1. The token system

- [ ] 1.1 `app/tokens.css` — every color property, declared once.
- [ ] 1.2 Move the scrubber's six in. **Do not touch its render path**; moving a
      declaration does not change the selectors that read it.
- [ ] 1.3 A test asserting no component stylesheet declares a color of its own,
      so the next surface cannot repeat `--severe`.

## 2. Scoping capture, without changing it

- [ ] 2.1 Capture's element styles move to `app/capture.module.css`.
- [ ] 2.2 `globals.css` keeps the reset, the type ramp and the token import.
- [ ] 2.3 **Screenshot capture before and after and compare.** This is the risky
      edit in the change: identical rendering is the only acceptable result.

## 3. The shells

- [ ] 3.1 `components/shell/` — a nav for desktop surfaces.
- [ ] 3.2 A footer for capture, **below** the capture control.
- [ ] 3.3 The night surface gets the nav; capture gets the footer.
- [ ] 3.4 Assert the policy options sit no lower than they do today.

## 4. The demo label

- [ ] 4.1 A component reading the served capability report.
- [ ] 4.2 Renders on `cloud`, absent otherwise. No build flag.

## 5. Verification

- [ ] 5.1 Capture measured no busier: policy visibility at keyboard-up
      viewports is unchanged from today's numbers.
- [ ] 5.2 320px and 1920px, no horizontal overflow.
- [ ] 5.3 Keyboard reachable; focus visible; the scrubber's slider role intact.
- [ ] 5.4 `npm run build` — static export still succeeds.
- [ ] 5.5 Full Python suite, web tests, typecheck, both guards.
- [ ] 5.6 `openspec validate --strict`.

## 6. Recorded, not built

- [ ] 6.1 **Capture hides the privacy choice with the keyboard up, and it does
      that today with no nav involved** — 0% visible at 390×300, 81% at 390×390.
      The fix is to put the policy choice above the textarea so the thing that
      falls off the bottom is never the privacy decision. That changes the shape
      of the 3am screen, so it is the subject's call and not a refactor's.
- [ ] 6.2 **`app/morning/`** — this unblocks it; `MORNING_INTERVIEW.md` owns it.
- [ ] 6.3 **Charts sharing the scrubber's time axis.** The component was built
      for three callers and this makes the second possible, not real. No chart
      surface exists to brush against yet.
