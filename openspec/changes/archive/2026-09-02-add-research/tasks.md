# Tasks — `research`

## 1. Redaction — the constitution-critical half

- [x] 1.1 `airlock/redact.py`: `build_query(text) -> str`. Term extraction, not
      filtering. **No second parameter of any kind.**
- [x] 1.2 Drop stopwords; drop capitalized non-sentence-initial tokens; drop
      credential-shaped tokens; cap length.
- [x] 1.3 The adversarial corpus, one constructed entry per leak category, in
      the test module. Labeled synthetic, with why the real four were not used.
- [x] 1.4 **The leak test**: no query contains any distinctive substring of its
      source entry. **Prove it can fail** — make `build_query` return its input
      and watch it go red.
- [x] 1.5 A signature test: `build_query` accepts exactly one parameter, so a
      bypass flag added later fails the build.

## 2. The provider

- [x] 2.1 `providers/tavily.py`: real HTTP, `urllib`/`json`, no SDK, mirroring
      `VllmReasoner`. `search` and `extract` only.
- [x] 2.2 `TavilyNotConfigured` when `TAVILY_API_KEY` is absent. Never a
      fabricated result.
- [x] 2.3 Quota responses raise `ToolQuotaExceeded`, which the existing taxonomy
      already maps to `tool_quota`.
- [x] 2.4 Register `TAVILY_API_KEY` in `config.SETTINGS` — secret-shaped, so the
      resolved view redacts it. The enumeration test will fail until this is done.
- [x] 2.5 The test stub lives in the test module, never in `providers/`.

## 3. The stage

- [x] 3.1 `night/research.py` or equivalent: refuse under `local-only` **before
      constructing a query**, skip with a reason when no credential is
      configured, otherwise search and record.
- [x] 3.2 Record through `Recorder.record_tool_call` — do not reimplement it.
- [x] 3.3 Wire into the night's research stage, replacing the
      `no research provider is configured` skip when a credential exists.

## 4. Verification

- [x] 4.1 A `local-only` run writes **zero** rows. Assert the count.
- [x] 4.2 Grep the whole database for a distinctive phrase; assert it appears in
      `entries` and nowhere else.
- [x] 4.3 Quota exhaustion records `tool_quota` and the run reaches `degraded`.
- [x] 4.4 Credits sum per run and match the individual calls.
- [x] 4.5 Cached results spend nothing.
- [x] 4.6 Full suite, both guards, `openspec validate --strict`.

## 5. Not done here, recorded rather than dropped

- [x] 5.1 **No live call was ever made.** No credential in this container, and
      obtaining one is a hard stop. The provider is unproven against the real API
      in exactly the way the reasoner was before the Spark ran it.
- [x] 5.2 **The leak list was not run against the real four entries.** They are
      on the always-on machine. The corpus here is synthetic and adversarial by
      construction; the real check is still owed.
- [x] 5.3 **No model-assisted query construction.** A `local-only` model would
      pick better search terms without changing the egress story. It is a real
      improvement and a separate argument.


## Mutations run

| Mutation | Result |
|---|---|
| `build_query` returns its input | **19 of 23** redaction tests red |
| Source order restored (drop the run repair) | `test_no_query_reproduces_a_run_of_its_source` red |
| The capitalization rule removed | 6 red, including the unknown-proper-noun case |

## Three defects the tests found in this change's own design

- **The query preserved word order.** "How does Contoso handle on-call rotations
  without burning people out?" became `handle on-call rotations without burning
  people` — six consecutive words, no names, and a fingerprint of the writer's
  phrasing. Leak-list category 8 arriving through a door the capitalization rule
  does not watch.
- **Sorting did not fix it, and a comment claimed it did.** The design note said
  "a sorted bag of terms cannot reproduce a phrase by construction." That is
  false: where the source words already run in alphabetical order the sorted
  query reproduces them, and `burning handle on-call rotations without` still
  carried a four-word run. The order is now **verified against the source and
  repaired by rotation**, so the guarantee is a checked postcondition rather
  than an argument about shuffling.
- **Two leak categories survived the first implementation.** `chemo` passed
  because it is lowercase and ordinary, and a private hostname passed because
  `_CONTACT_SHAPED` anchors on `$` and the span still carried its trailing
  period. Both fixed; both have a corpus row.

## What is honest about the sensitive-topic list

`_SENSITIVE` is the one place this module **filters rather than constructs, and
it fails open**. A health, legal or financial term not on it passes. It is a
backstop for the category the capitalization rule cannot reach, not a mechanism,
and an exhaustive list of what a person might not want searched does not exist.
Stated in the module, in the spec, and here.

## The queries this produces, read beside their entries

```
entry: How does Contoso handle on-call rotations without burning people out?
query: on-call rotations burning handle

entry: What are people doing about agent memory systems that either forget
       everything or remember too much?
query: agent forget memory remember systems

entry: Work out how Northwind Health should stage the Halyard rollout without
       burning the support team out.
query: burning rollout stage support team without work
```

The second is a genuinely good search. The first and third are **mediocre** —
"work" and "handle" are noise, and a person would have written something
sharper. That is the accepted trade, stated in the proposal before it was
measured: a mediocre query that leaks nothing beats a good one that leaks.

## Still owed

- **No live call was ever made.** No credential, and obtaining one is a hard
  stop. The provider is unproven against the real API.
- **The leak list has not been run against the real four entries.** The corpus
  here is synthetic and adversarial by construction.
