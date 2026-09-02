# Tasks — `configuration`

Sequential unless noted. Each item leaves the suite green.

## 1. The registry

- [ ] 1.1 Add a `Setting` record to `secondshift/config.py`: name, what reads it,
      whether it is required, whether it is secret-shaped, and a one-line
      description. `SECOND_SHIFT_RUBRIC_OVERWRITE` is marked shell-read.
- [ ] 1.2 Add `SETTINGS`, the registry of all thirteen. Enumerated from the tree,
      not from `docs/prompts/CONFIGURATION.md` — that document said ten.
- [ ] 1.3 Write the enumeration test first: scan `apps/api/secondshift`, `deploy`
      and `scripts` for `SECOND_SHIFT_[A-Z_]+` and assert the registry knows each.
      **Prove it can fail**: add a throwaway read in a module, watch the suite go
      red, remove it. Record the mutation in the test's docstring.

## 2. Loud-on-malformed

Independent of section 1; can run in parallel with it.

- [ ] 2.1 `_local_config` and `_embedder_config`: distinguish absent (default)
      from present-and-unparseable (raise, naming the file). Keep `OSError` on a
      missing file as the default path.
- [ ] 2.2 `api/location.home_location`: same distinction. An absent file still
      yields no coordinates; a malformed one raises naming the file.
- [ ] 2.3 `telemetry/pricing.PricingTable.load`: wrap the parse so the error
      names the file. The missing-file case already names it — do not change it.
- [ ] 2.4 `SECOND_SHIFT_SYNTHETIC`: a shared parser that accepts documented true
      and false spellings and raises on anything else, used by `api/main.py`.
- [ ] 2.5 Tests for each: absent defaults, malformed raises, the message names
      the file. Assert on the file name appearing in the message, not just the
      exception type — an error that does not say which file is the defect being
      fixed.

## 3. Resolution with provenance

- [ ] 3.1 `resolve_all()` returning a resolved value and origin per setting.
      Origin is `environment`, a file path, or `default`.
- [ ] 3.2 It calls the existing resolvers rather than reimplementing precedence.
      A second copy that can drift from `config.py` is on the never-ship list.
- [ ] 3.3 Redaction for secret-shaped names, reporting set-ness and origin
      without the value.
- [ ] 3.4 Precedence test: environment, then file, then default, all three
      asserted for at least one setting, with the reported origin checked each
      time — not just the value.

## 4. The command

- [ ] 4.1 `secondshift/config/__main__.py` — or `__main__` handling in the
      existing module — for `python -m secondshift.config show`.
- [ ] 4.2 Aligned output: name, value, origin. A reader on the always-on machine
      fixes a wrong setting without opening a `.py`.
- [ ] 4.3 Exit zero when every required setting resolved, non-zero naming the
      one that did not.
- [ ] 4.4 Test it runs with an empty environment, no config files, no database
      and no brain, and does not raise.
- [ ] 4.5 Assert no model identifier is embedded — `test_providers.py`'s source
      scan already fails the build on one; confirm it still passes rather than
      assuming.

## 5. Verification

- [ ] 5.1 Full suite green. `scripts/check-no-environment.sh` and
      `scripts/check-american-english.sh` clean.
- [ ] 5.2 `bash -n deploy/spark/deploy.sh` if it is touched.
- [ ] 5.3 `openspec validate 2026-09-02-add-configuration --strict`.
- [ ] 5.4 Paste the real `config show` output into the report.

## Deferred, recorded rather than dropped

**Per-role `max_tokens`.** `docs/SPEC_ROADMAP.md` parks this here, out of
`agents`. It is not built: the `[agents]` block shape depends on what
`night-pipeline` needs per stage, and a shape guessed now is one that gets
rewritten. `LocalReasonerSettings.max_tokens` remains global. Whoever builds
`night-pipeline` owns picking the shape; this note is the handoff.
