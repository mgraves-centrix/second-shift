# Tasks — `research`

## 1. Redaction — the constitution-critical half

- [ ] 1.1 `airlock/redact.py`: `build_query(text) -> str`. Term extraction, not
      filtering. **No second parameter of any kind.**
- [ ] 1.2 Drop stopwords; drop capitalized non-sentence-initial tokens; drop
      credential-shaped tokens; cap length.
- [ ] 1.3 The adversarial corpus, one constructed entry per leak category, in
      the test module. Labeled synthetic, with why the real four were not used.
- [ ] 1.4 **The leak test**: no query contains any distinctive substring of its
      source entry. **Prove it can fail** — make `build_query` return its input
      and watch it go red.
- [ ] 1.5 A signature test: `build_query` accepts exactly one parameter, so a
      bypass flag added later fails the build.

## 2. The provider

- [ ] 2.1 `providers/tavily.py`: real HTTP, `urllib`/`json`, no SDK, mirroring
      `VllmReasoner`. `search` and `extract` only.
- [ ] 2.2 `TavilyNotConfigured` when `TAVILY_API_KEY` is absent. Never a
      fabricated result.
- [ ] 2.3 Quota responses raise `ToolQuotaExceeded`, which the existing taxonomy
      already maps to `tool_quota`.
- [ ] 2.4 Register `TAVILY_API_KEY` in `config.SETTINGS` — secret-shaped, so the
      resolved view redacts it. The enumeration test will fail until this is done.
- [ ] 2.5 The test stub lives in the test module, never in `providers/`.

## 3. The stage

- [ ] 3.1 `night/research.py` or equivalent: refuse under `local-only` **before
      constructing a query**, skip with a reason when no credential is
      configured, otherwise search and record.
- [ ] 3.2 Record through `Recorder.record_tool_call` — do not reimplement it.
- [ ] 3.3 Wire into the night's research stage, replacing the
      `no research provider is configured` skip when a credential exists.

## 4. Verification

- [ ] 4.1 A `local-only` run writes **zero** rows. Assert the count.
- [ ] 4.2 Grep the whole database for a distinctive phrase; assert it appears in
      `entries` and nowhere else.
- [ ] 4.3 Quota exhaustion records `tool_quota` and the run reaches `degraded`.
- [ ] 4.4 Credits sum per run and match the individual calls.
- [ ] 4.5 Cached results spend nothing.
- [ ] 4.6 Full suite, both guards, `openspec validate --strict`.

## 5. Not done here, recorded rather than dropped

- [ ] 5.1 **No live call was ever made.** No credential in this container, and
      obtaining one is a hard stop. The provider is unproven against the real API
      in exactly the way the reasoner was before the Spark ran it.
- [ ] 5.2 **The leak list was not run against the real four entries.** They are
      on the always-on machine. The corpus here is synthetic and adversarial by
      construction; the real check is still owed.
- [ ] 5.3 **No model-assisted query construction.** A `local-only` model would
      pick better search terms without changing the egress story. It is a real
      improvement and a separate argument.
