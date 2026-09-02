# Design — `research`

## Context

`tool_calls.query_redacted` has carried the requirement in its own name since
`0001_initial.sql`, with a comment saying the raw query is never stored. The
airlock has `policy.py`, `capability.py` and `quarantine.py` — and **no
redaction module**. This adds it.

## Decision 1 — redaction is construction, not filtering

The naive shape is `redact(entry_text) -> safe_text`, then search that. Rejected,
and this is the design's central claim.

A filter has to *recognize* everything dangerous. It fails open: a proper noun it
does not know, a codename that looks like a common word, a phrasing that is
distinctive without containing any keyword — all pass through. And the last of
those is not a gap in the filter, it is a category the filter cannot address at
all. Six distinctive words are enough to identify who wrote something.

So the raw text is **never a candidate to become a query**. `build_query`
extracts topical terms and assembles a query from them:

```
entry text ──> tokenize ──> drop stopwords
                        ──> drop capitalized non-sentence-initial tokens
                        ──> drop anything credential-shaped
                        ──> cap length
                        ──> join
```

It fails *closed*: a token has to earn its way into the query. An unrecognized
proper noun is dropped because it is capitalized, not because it is on a list.

**Alternative considered:** a named-entity recognizer. Rejected — it adds a model
dependency to the one path that must not have one, it installs badly on aarch64
(the fifth wheel this project has avoided), and it fails open on exactly the
codenames category 3 cares about most.

**The cost, stated:** dropping every capitalized token loses legitimate search
terms — "Rust", "Kubernetes", "SQLite". Queries are worse than a human would
write. That is the accepted trade, and it is why the follow-up is a *local*
model improving term selection rather than a longer allowlist.

## Decision 2 — no bypass, enforced by a test on the signature

`redact.build_query(text: str) -> str`. No `enabled=`, no `strict=`, no
`policy=` that could select a weaker path.

Principle 2 says a flag that turns redaction off is a violation *even if it
defaults to on*, so the guard is not "the default is safe" but "there is no
parameter". A test reads the function's signature via `inspect` and fails if it
grows one. That test is what makes the rule enforceable rather than remembered.

**Alternative considered:** a `strict: bool = True` for a future "the subject
explicitly approved this query" path. Rejected — that path does not exist, and
the parameter would exist before the use case, which is how a default gets
flipped in a later change nobody reads.

## Decision 3 — `local-only` is refused above the provider

The check is in the research stage, before the provider is constructed, not
inside `TavilyProvider`. Two reasons:

- The provider is the wrong place for a policy decision. `assert_permitted`
  already establishes that pattern for reasoners.
- A refusal inside the provider would still have built the query. Refusing above
  it means the raw text is never even tokenized under `local-only`.

The seed already models the behavior and has a test asserting it: a local-only
night writes zero `tool_calls`. This implements the same rule in the real path.

## Decision 4 — the provider is real, and unreachable without a credential

`TavilyProvider` makes real HTTP against the documented endpoints, mirroring
`VllmReasoner`: `urllib`/`json`, no SDK, no new dependency.

It reads `TAVILY_API_KEY` and raises `TavilyNotConfigured` when it is absent.
**It never fabricates a result.** The stub used in tests lives in the test
module, not in `providers/`, so there is no importable object that could return
convincing search results into a live path — the property `EchoReasoner`
establishes by returning its own input.

**Consequence, accepted:** the provider has never made a real call. It is
unproven against the live API in exactly the way the reasoner was unproven
against the live model before the Spark ran it, and it is named as such rather
than implied to work.

## Decision 5 — credits are recorded per call and summed by a view, not a column

`tool_calls.credits` already exists per row. A run's research spend is
`SUM(credits)` over the run — derived, never stored, matching the convention
`docs/DATA_MODEL.md` states as *counters are views, never stored columns*.

`run_cost` already selects `tool_credits` as a correlated subquery over
`tool_calls`, so the summing exists and this change writes the rows it reads. No
new view is needed, which is why none is added.
