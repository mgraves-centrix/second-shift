## 1. The judge

- [x] 1.1 `ModelJudge` in `evals/judge.py`, satisfying the `Judge` protocol
      against any `Reasoner`. `name` reads `reasoner.model` at runtime, so no
      model identifier appears outside `providers/` and the source scan in
      `test_providers.py` stays green.
- [x] 1.2 `policy` and `version` are required constructor arguments with no
      defaults. A default policy is a remote call nobody chose; a default
      version is a pin that floats.
- [x] 1.3 The prompt asks for one JSON object with the five rubric dimensions,
      carrying the rubric text and the output being graded. The rubric arrives
      as text from the caller — the judge never loads a file, because the hash
      the run pinned belongs to whoever read it.
- [x] 1.4 No telemetry written here. `Reasoner.complete` records the call, the
      failure and the unclean stop; a judge that recorded its own would be a
      second writer.

## 2. Reading the judgement

- [x] 2.1 The last top-level JSON object in the completion, found by scanning
      for balanced braces rather than by regex. A regex for nested JSON is
      either wrong or unreadable, and this one has to be read by whoever
      debugs a refused run at 2am.
- [x] 2.2 Refuse a completion that did not stop cleanly, **before** parsing.
      `Completion.finish_reason` is carried through for exactly this.
- [x] 2.3 Refuse with `UnreadableJudgement`, which `EvalRunner.score` already
      catches as a failed sample and records as a typed failure — so a judge
      that cannot read an answer leaves the run incomplete rather than scored.
- [x] 2.4 String content inside the object is not scanned for braces. A rubric
      note containing `}` would otherwise truncate the object, and the note is
      the one field a model is likely to write freely.

## 3. Verification against a real endpoint

- [x] 3.1 `VllmStub` serves each shape: bare object, fenced object,
      deliberation then object, two objects, prose only, truncated, a value
      outside 1–5, a missing dimension. One test each.
- [x] 3.2 The model call is recorded even when the judgement is refused, read
      from `model_calls` rather than asserted on a mock.
- [x] 3.3 `EvalRunner.score` driven end to end with `ModelJudge` over the stub,
      asserting the run reports the stub's served model as its judge.
- [x] 3.4 One mutation: the truncation refusal removed. It is the silent one —
      a smaller valid object, scored — and the gate must go red.

## 4. What this cannot verify here

- [x] 4.1 Say so in the proposal's Risk section rather than in a commit
      message: a stub cannot predict what a real checkpoint emits around its
      JSON, so the first real completion is the verification.
- [x] 4.2 Record the machine task in `docs/SPEC_ROADMAP.md` under *Owed
      verification*, where a reader deciding what a machine session should do
      will find it, rather than in a checkbox inside an archive.

## 5. Gate

- [x] 5.1 `python3 scripts/gate.py` green, run unpiped so the exit code is the
      gate's own.
