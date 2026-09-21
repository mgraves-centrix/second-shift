# Tasks — the API layer

Sequential except where noted. Task 1 must land before anything moves; it is the
only thing standing between a refactor and a rewrite.

## 1. Characterize before moving anything

- [x] 1.1 Seed a fixed database (`--seed 42`) and capture every route's status,
      content type and body to a fixture file checked into the test tree.
- [x] 1.2 Write the equality test against those fixtures. It runs against the
      current, unsplit `app.py`.
- [x] 1.3 **Prove it can fail**: rename one field in a response model, watch the
      test go red, revert. Record what the failure said. A test that stays green
      here is comparing nothing and the rest of this change is unverified.
- [x] 1.4 Capture the routes with no fixture-able body too — `/artifacts/{id}`
      returns bytes and a content type, and its 404s are three distinct
      messages. Those are part of the contract.

## 2. Lift the context out

- [ ] 2.1 `api/context.py`: move `Context` and `build_context` verbatim; add
      `get_context(request)` reading `request.app.state.context`.
- [ ] 2.2 `app.py` re-exports `Context` and `build_context`, so
      `from secondshift.api.app import Context, create_app` keeps working. Three
      test files and `main.py` import from there.
- [ ] 2.3 `create_app` sets `app.state.context` before including anything.
- [ ] 2.4 Gate. No test modified.

## 3. Lift the mappers out

- [ ] 3.1 `api/mappers.py`: `capability_payload`, `run_summary`, `model_call`,
      `entry_response` — moved verbatim, underscore dropped since they are now
      imported across modules.
- [ ] 3.2 Gate. No test modified.

## 4. One module per capability

Each step is its own commit and its own gate run, so a byte difference is
attributable to the module that caused it.

- [ ] 4.1 `routes/system.py` — `/health`, `/capabilities`.
- [ ] 4.2 `routes/capture.py` — `/entries`. **This is the route that must not
      break**; capture is live and taking real ideas. Run the replay and the
      disagreeing-instant cases directly after this step, not at the end.
- [ ] 4.3 `routes/night.py` — `/runs`, `/runs/{id}/timeline`, `/events/{id}`.
- [ ] 4.4 `routes/morning.py` — `/morning`, `/decisions/{id}/answer`.
- [ ] 4.5 `routes/artifacts.py` — `/artifacts/{id}`.
- [ ] 4.6 `routes/__init__.py` documents the rule and both exceptions
      (`/events` under night, `/decisions` under morning), because a rule with
      unwritten exceptions is not a rule.
- [ ] 4.7 Each route keeps its docstring. Several are the only written record of
      why a route is shaped the way it is — the decision id in the path, the
      timeline's missing payload field, the morning GET that does not advance
      its own boundary.

## 5. Guard the mount

- [ ] 5.1 `create_app` raises if anything is registered after the static mount.
- [ ] 5.2 Test: construct an app with a route registered after the mount, assert
      construction fails.
- [ ] 5.3 Test: `GET /runs` returns JSON, not the exported page.

## 6. Prove the split did what it claims

- [ ] 6.1 Byte-equality test passes against the split layer.
- [ ] 6.2 Orphan check: every public symbol in `context.py`, `mappers.py` and
      each route module is referenced from outside its module. Anything that is
      not was moved without a caller and should not have been moved.
- [ ] 6.3 Mutation pass: break the mount guard, break one mapper, break the
      `app.state` lookup. Each must turn something red.
- [ ] 6.4 Confirm `git diff --stat` on `apps/api/tests/` shows only additions.
      A modified test means the contract moved.
- [ ] 6.5 Count: add a route to a scratch branch and check it touches one file.
      That is the success measure; measure it rather than assert it.

## 7. Correct what grounding this turned up

- [ ] 7.1 `nebius-executor`'s proposal lists "an authenticated telemetry ingest
      route" as a deliverable while its own decisions section resolves against
      building one. Correct the deliverables line to match the resolution.
      `tasks.md` and the spec are already consistent with it; only that line is
      wrong, and it is what put a question into `API_LAYER.md` that did not need
      asking.
- [ ] 7.2 `docs/ARCHITECTURE.md:106` says `api/` holds "app.py, schemas,
      endpoint modules". After this it is true. Update it to name the actual
      modules rather than leave it vague enough to have been true all along.

## 8. Ship

- [ ] 8.1 `python3 scripts/gate.py` green, all ten.
- [ ] 8.2 `openspec validate --strict`, sync specs, archive.
- [ ] 8.3 `docs/SPEC_ROADMAP.md`: mark `api-layer` shipped, and record that its
      scheduling argument had already been spent — three of the five sessions it
      was meant to de-collide ran in sequence first.
