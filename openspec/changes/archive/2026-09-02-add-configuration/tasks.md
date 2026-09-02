# Tasks — `configuration`

Sequential unless noted. Each item leaves the suite green.

## 1. The registry

- [x] 1.1 Add a `Setting` record to `secondshift/config.py`: name, what reads it,
      whether it is required, whether it is secret-shaped, and a one-line
      description. `SECOND_SHIFT_RUBRIC_OVERWRITE` is marked shell-read.
- [x] 1.2 Add `SETTINGS`, the registry of all thirteen. Enumerated from the tree,
      not from `docs/prompts/CONFIGURATION.md` — that document said ten.
- [x] 1.3 Write the enumeration test first: scan `apps/api/secondshift`, `deploy`
      and `scripts` for `SECOND_SHIFT_[A-Z_]+` and assert the registry knows each.
      **Proved it can fail**: `os.environ.get("SECOND_SHIFT_THROWAWAY")` added to
      `brain/repo.py` turned it red naming that variable; removing it turned the
      suite green. Recorded in the test module's docstring. Three further
      mutations were run and are listed at the bottom of this file.

## 2. Loud-on-malformed

Independent of section 1; can run in parallel with it.

- [x] 2.1 `_local_config` and `_embedder_config`: distinguish absent (default)
      from present-and-unparseable (raise, naming the file). Keep `OSError` on a
      missing file as the default path.
- [x] 2.2 `api/location.home_location`: same distinction. An absent file still
      yields no coordinates; a malformed one raises naming the file.
- [x] 2.3 `telemetry/pricing.PricingTable.load`: wrap the parse so the error
      names the file. The missing-file case already names it — do not change it.
- [x] 2.4 `SECOND_SHIFT_SYNTHETIC`: a shared parser that accepts documented true
      and false spellings and raises on anything else, used by `api/main.py`.
- [x] 2.5 Tests for each: absent defaults, malformed raises, the message names
      the file. Assert on the file name appearing in the message, not just the
      exception type — an error that does not say which file is the defect being
      fixed.

## 3. Resolution with provenance

- [x] 3.1 `resolve_all()` returning a resolved value and origin per setting.
      Origin is `environment`, a file path, or `default`.
- [x] 3.2 It calls the existing resolvers rather than reimplementing precedence.
      A second copy that can drift from `config.py` is on the never-ship list.
- [x] 3.3 Redaction for secret-shaped names, reporting set-ness and origin
      without the value.
- [x] 3.4 Precedence test: environment, then file, then default, all three
      asserted for at least one setting, with the reported origin checked each
      time — not just the value.

## 4. The command

- [x] 4.1 `secondshift/config/__main__.py` — or `__main__` handling in the
      existing module — for `python -m secondshift.config show`.
- [x] 4.2 Aligned output: name, value, origin. A reader on the always-on machine
      fixes a wrong setting without opening a `.py`.
- [x] 4.3 Exit zero when every required setting resolved, non-zero naming the
      one that did not.
- [x] 4.4 Test it runs with an empty environment, no config files, no database
      and no brain, and does not raise.
- [x] 4.5 Assert no model identifier is embedded — `test_providers.py`'s source
      scan already fails the build on one; confirm it still passes rather than
      assuming.

## 5. Verification

- [x] 5.1 Full suite green. `scripts/check-no-environment.sh` and
      `scripts/check-american-english.sh` clean.
- [x] 5.2 `bash -n deploy/spark/deploy.sh` if it is touched.
- [x] 5.3 `openspec validate 2026-09-02-add-configuration --strict`.
- [x] 5.4 Paste the real `config show` output into the report.

## Deferred, recorded rather than dropped

**Per-role `max_tokens`.** `docs/SPEC_ROADMAP.md` parks this here, out of
`agents`. It is not built: the `[agents]` block shape depends on what
`night-pipeline` needs per stage, and a shape guessed now is one that gets
rewritten. `LocalReasonerSettings.max_tokens` remains global. Whoever builds
`night-pipeline` owns picking the shape; this note is the handoff.


## Mutations run, and what each proved

A test that has never failed is a claim. Each of these was applied, the named
test watched go red, and the mutation reverted.

| Mutation | Test that went red |
|---|---|
| `os.environ.get("SECOND_SHIFT_THROWAWAY")` added to `brain/repo.py` | `test_every_variable_read_anywhere_is_registered`, naming the variable |
| `_check_endpoint` stops reading `models_config_error()` | `test_the_probe_blames_the_file_rather_than_the_network` — it reverted to reporting `unreachable`, which is the original defect |
| `_origin_of` always returns `Origin.DEFAULT` | `test_environment_beats_file_beats_default` and `test_a_file_sourced_value_names_the_file` |
| `synthetic_flag` returns `False` instead of raising | all three refusal tests |

The third is the one worth keeping: asserting only the *value* of a resolved
setting would have passed against a view that reports every origin as `default`,
which is precisely what this capability exists to fix. The origin is asserted
alongside the value at every layer.
