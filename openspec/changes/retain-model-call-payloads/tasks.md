## 1. The payload store

- [ ] 1.1 `apps/api/secondshift/telemetry/payloads.py`: `default_root()` of
  `~/second-shift-data/payloads`, `payload_root()` reading
  `SECOND_SHIFT_PAYLOADS`, and `relative_paths(model_call_id, ts_ms)` returning
  the prompt and completion paths under `<yyyy-mm>/`. Verify: a unit test that
  the two paths differ only in suffix, that the month comes from the timestamp
  rather than from now, and that neither path is absolute.
- [ ] 1.2 `write_payload(...)` in the same module: writes both files, reads both
  back, returns what landed. Mirrors `artifacts/store.py` — byte counts from the
  read-back, never from the text passed in. Verify: a test that a short write
  is reported at the length of the file on disk, and a test that the prompt file
  holds every message's role and content as JSON.
- [ ] 1.3 Register `ENV_PAYLOADS = "SECOND_SHIFT_PAYLOADS"` in `config.py`
  beside `ENV_ARTIFACTS`, including in `resolve_all` so `config show` reports
  it. Verify: the existing settings test that enumerates resolved settings sees
  it, and `apps/api/.venv/bin/python -m secondshift.config show` prints it.

## 2. Retention on the one path every completion takes

- [ ] 2.1 `Recorder.record_model_call_payload(...)`: the file write outside the
  writer lock, the row insert inside it, `training_eligible = not is_synthetic`
  and `redacted` from the caller. Returns the relative paths. Verify: a test
  that the row exists with the paths and byte counts, and that a synthetic call
  is recorded ineligible.
- [ ] 2.2 On a failed write: catch `OSError`, record a typed failure through the
  recorder, write no row, return nothing. Verify: a test with an unwritable root
  asserting the completion is still returned, the `model_calls` row still
  exists, a `failures` row exists, and `model_call_payloads` is empty.
- [ ] 2.3 Call it from `Reasoner.complete` in `providers/base.py`, after
  `record_model_call`. Verify: a test driving a provider that overrides only
  `_do_complete` and contains no retention code, asserting its completion was
  retained — the "implementation cannot skip retention" scenario.
- [ ] 2.4 One mutation in `scripts/check-mutations.py`: retention removed from
  `Reasoner.complete`, naming the test that catches it. This is the defect being
  closed, so it is the one mutation that must exist.

## 3. A score points at what was scored

- [ ] 3.1 `EvalRunner._record_result` writes `output_path` from the retained
  completion path of the generating call, and writes NULL where nothing was
  retained rather than a path to a missing file. Verify: a test that a scored
  sample's `output_path` names a file that exists and holds the generated text,
  and a test that an unretained sample records NULL.

## 4. A backup that carries them

- [ ] 4.1 `ops/backup.py`: a `PAYLOADS` member name, `create_backup` copying the
  payload root, and `payload_files` / `payload_bytes` on `Manifest`. Verify: a
  test that a backup of a tree holding payload files reports both counts and
  that every copied file appears in `members` with a digest.
- [ ] 4.2 `ops/restore.py`: restore the payload tree under the same
  `--overwrite` rule the artifacts tree already follows. Verify: a test that a
  round trip returns byte-identical payload files, and that restoring without
  `--overwrite` over an existing root is refused.
- [ ] 4.3 `ops/__main__.py`: print the payload count beside the artifact count
  on both `backup` and `restore`, and read the payload root through
  `config.resolve_all` like the other two paths. Verify: a test on the printed
  output, since `CONTAINS` is printed in the same breath and the claim is the
  point.
- [ ] 4.4 One mutation: the payload copy removed from `create_backup`, naming
  the test that catches it. `CONTAINS` was false for seven weeks with a green
  suite.

## 5. The documents that were wrong

- [ ] 5.1 `docs/operations/RECOVERY.md`: the backup section says what a backup
  now carries and that the payload tree is part of it. Verify:
  `python3 scripts/check-drift.py` passes and the restore-executed note stays
  accurate.
- [ ] 5.2 `docs/DATA_MODEL.md`: the `model_call_payloads` paragraph says where
  the root is configured and that retention happens in the provider base class.
  Verify: the same drift check.
- [ ] 5.3 `docs/operations/reports/README.md` and the 16 Oct report's finding:
  note where the finding was closed, without rewriting the dated record of what
  was true that day. Verify: read both; the report stays a report.

## 6. The whole gate

- [ ] 6.1 `GATE_CHROME=/opt/pw-browsers/chromium-1194/chrome-linux/chrome
  python3 scripts/gate.py` green, including the two new mutations and the
  derived mutation count in `docs/SUBMISSION.md`.
- [ ] 6.2 `npx openspec validate retain-model-call-payloads --strict` clean, then
  commit and push.
