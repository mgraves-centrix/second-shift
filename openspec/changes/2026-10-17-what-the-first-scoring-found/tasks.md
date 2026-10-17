## 1. Every completion keeps what it said

- [x] 1.1 `Reasoner.complete` hands messages, completion and finish reason to
      `Recorder.record_payload`; files are written before the row, paths are
      relative to the root, sizes are read back from disk.
- [x] 1.2 A write that fails records a failure scoped `payload` and the caller
      still receives its completion.
- [x] 1.3 `SECOND_SHIFT_PAYLOADS` is a registered, required setting defaulting
      beside the database; `conftest` isolates it per test.
- [x] 1.4 Tests: `test_payloads.py`, including a root that cannot be written.

## 2. A backup carries them

- [x] 2.1 `create_backup` and `restore_backup` take `payloads_root` with no
      default; the manifest counts payload files and bytes; a manifest without
      the counts verifies and restores as an older backup.
- [x] 2.2 `ops` resolves the root through the setting and takes `--payloads`;
      the backup unit names it; `RECOVERY.md` lists `payloads/`.
- [x] 2.3 Tests: `test_backup_payloads.py`; every existing call site in
      `test_operations.py` passes the root, because the contract changed.
- [x] 2.4 On the machine: a backup taken after the first payload-capturing run
      holds payload files and `ops verify` passes it. 17 Oct, the scoring copy's
      70 payload files — 35 calls, 1.09 MB — onto the NAS in a directory apart
      from production's, so `doctor`'s view of real backups is not muddied:
      110 members intact, all 70 payload files among them.

## 3. A refused judgement can be read back

- [x] 3.1 `UnreadableJudgement` carries the judge's model call; the failure's
      context names the judge's call and the answer's.
- [x] 3.2 `eval_results.output_path` is the scored answer's kept completion.

## 4. A run is scored once

- [x] 4.1 `score` refuses a run holding any result, before generating anything,
      and the command exits 2 with the reason.
- [x] 4.2 `status` names an interrupted run — results recorded, judge never
      written back — as interrupted rather than awaiting scoring.

## 5. The judge is pinned by what it asks

- [x] 5.1 `ModelJudge.version` is the configured pin and the hash of the ask.
- [x] 5.2 The curve refuses two judge versions. The derived count of its
      refusals moves from ten to eleven in the three documents that cite it.

## 6. The reader, from evidence

- [x] 6.1 On the machine, with payloads kept, score a copy under week-8
      conditions and read the refused judgements. Recorded here by shape, never
      by text. Run `01M547MSED55JF2RP4RS7TKQ0Y` on a restored copy, 17 Oct: one
      judgement refused with the same `char 29` the 16 Oct refusals showed. Its
      completion held three objects of the judgement's form — the template
      echoed with `<1-5>` placeholders at char 25,332, a draft that does not
      decode at 31,957, and a valid judgement at 32,642. The draft's stray quote
      left `last_object`'s forward scan inside a "string" for the rest of the
      text, so it never saw the final object and returned the echo.
- [x] 6.2 Fix the cause the evidence shows, test-first against that shape — which
      turned out to be the reader, not the ask. The last object opening with
      `"scores"` is decoded from where it starts, nothing before it affects the
      reading, and a malformed final object is refused rather than replaced by
      an earlier draft. `_ASK` is unchanged; `Judgement.parse` is unchanged.
      The reader is hashed into the judge's version beside the ask.
- [x] 6.3 Measure before and after on the same completions: every judge
      completion kept on the copy, re-read by both readers. 17 kept; the old
      reader read 15, the new reads all 17. The two differences are the two
      refusals — in the second, the final judgement had been restated three
      times identically after four malformed drafts — and no score the old
      reader could read changed. The run finished 15 of 18; under the new
      reader it would have been 17, the one remaining sample being 6.4's.
- [x] 6.4 A second failure mode, which is not the judge's: an answer that ran to
      the 16,000-token limit without finishing (`TurnDidNotFinish`). Refused
      correctly — a truncated answer graded is a wrong number. Whether a failed
      sample may be generated again is a methodology decision and is put to the
      subject rather than made here; see 7.2.

## 7. The week-8 measurement

- [ ] 7.1 Record a fresh week-8 baseline. `01M53FX6MV5D9ZWF4Z6117YVSE` was
      interrupted on 16 Oct and cannot be scored.
- [ ] 7.2 Take a backup, then score week 8 and week 1 in one sitting under the
      pinned judge. Blocked on the subject's answer to 6.4: at the rate observed,
      an 18-sample run with no failed sample is not the likely outcome, and an
      incomplete week 1 cannot be retaken.
- [ ] 7.3 `python -m secondshift.evals curve`, and record the verdict with its
      standard error, or the refusal with its cause.

## 8. The commands find their content from anywhere

- [x] 8.1 The default prompt, rubric and threshold paths resolve from the
      package's location, which is the same in a clone and the deployed tree.

## 9. Gate

- [ ] 9.1 `python3 scripts/gate.py` green, run unpiped.
