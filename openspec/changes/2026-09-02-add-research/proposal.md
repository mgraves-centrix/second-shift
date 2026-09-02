# Add `research` — the only stage that talks to the open internet

## Scale classification

**L3 — Epic.** It is the system's first outward egress path, so constitution
principle 2 governs it as a blocking constraint rather than a consideration; it
writes a column (`tool_calls.query_redacted`) whose *name* is the requirement;
and the redaction it introduces is the mechanism every later capability inherits.
Design doc included.

## Why

Research is the only stage where a half-formed 3am idea can leave the machine
verbatim to a third party. The schema was built expecting exactly that:

```sql
query_redacted  TEXT,  -- redacted per policy; raw query is never stored
```

The column is not called `query`. **Nothing has ever written it** — verified
against the tree: `Recorder.record_tool_call` exists and is tested, and the only
caller is `packages/seed/`.

## Two things this change could not do, stated before anything else

**1. There is no usable Tavily credential in this container.** `TAVILY_API_KEY`
is unset; `~/.tavily/session.json` exists but `tvly auth` reports *Not
authenticated*. Obtaining or rotating one is a hard stop, so none was sought.

The prompt says to write the proposal and stop rather than stub it, and the
*reason* it gives is precise: a stub returning plausible results is
indistinguishable in `tool_calls` from a real search, and credit accounting is a
scored artifact. **That risk is avoided rather than accepted.** No provider that
fabricates results is bound into the runtime path. With no credential
configured, the research stage stays `skipped` with a recorded reason — exactly
as it does today — so **not one row reaches `tool_calls`**. What ships is the
redaction, the real provider that makes real HTTP, and hermetic tests against an
inert stub, which the prompt's own verification section requires.

**2. The adversarial corpus the prompt specifies was not reachable.** It says to
build the leak list from "the four real entries in the database and the brain's
`profile.md`". The container's database holds **zero** entries and
`../second-shift-brain` is absent — both live on the always-on machine. And the
real subject-authored text that *is* in the repository,
`config/evals/candidates.md`, is **pre-sanitized** because the repository is
public: a redaction test against it would pass with redaction deleted, which is
the definition of a test that proves nothing.

So the corpus below is **synthetic and adversarial by construction**, one entry
per leak category. It is labeled as such in the test module. **Re-running the
list against the real four is a named follow-up**, and it is the check this
substitute cannot perform.

## The open decision — what redaction removes

Enumerated as categories, each with a constructed entry that carries it. "Strip
an email address" is not an answer; the failure the constitution names is an
*idea* leaving, and an idea leaks through proper nouns long before it leaks
through an `@`.

| # | Leak category | What a naive query would carry | What redaction does |
|---|---|---|---|
| 1 | **Named third party** — a client, a partner, a vendor | `"onboarding flow for Northwind Health"` | Drop the proper noun. The searchable question is about onboarding flows, not about who. |
| 2 | **Employer / affiliation** | `"how does Contoso handle on-call"` | Same. The org is never the search term. |
| 3 | **Unreleased product or codename** | `"pricing page for Project Halyard"` | Drop it. A codename is the single highest-value token to a competitor and the least useful to a search engine. |
| 4 | **Person by name** — colleague, report, family | `"how to give Priya feedback about deadlines"` | Drop the name; the question is about feedback and deadlines. |
| 5 | **Health, legal or financial specifics** | `"managing standups around my chemo schedule"` | Drop the specific; generalize to the workplace question or drop the entry from research entirely. |
| 6 | **Credential-shaped strings** — keys, tokens | a key pasted into an idea by accident | Never leaves, and never reaches a log. This is the one case where the right answer is to refuse the call. |
| 7 | **Location and hostnames** | a tailnet name, a home address | Drop. `scripts/check-no-environment.sh` already enforces this for tracked files; egress needs the same rule at runtime. |
| 8 | **Verbatim phrasing itself** | the entry echoed as the query | The query is *constructed*, never the entry text. A distinctive 6-word phrase is enough to identify a person's writing. |

**Category 8 is the load-bearing one and it drives the design.** Categories 1–7
are things to remove; 8 is a thing not to do. A redactor that removes proper
nouns from raw entry text still ships the subject's sentence structure and
distinctive phrasing to a third party. So redaction is **not** a filter applied
to the entry — the query is built from extracted topical terms, and the raw text
is never a candidate to become a query in the first place.

That is why the test is "no query contains any distinctive substring of its
source entry" rather than "no query contains a name."

## The second open decision — where query construction runs

**Locally, on every profile, always.**

Under `cloud-assisted`, having a remote model turn the entry into search terms
would send the entry to Token Factory to produce the query — the same disclosure
as the query itself, one hop earlier. That would make redaction theater.

So query construction is **not a model call at all**. It is deterministic term
extraction in `airlock/redact.py`: stopword removal, proper-noun dropping, and a
length cap, running in-process with no provider. This has three consequences
worth stating:

- It is **auditable**. A person can read the query beside the entry and judge it,
  which is what the prompt asks the test to be.
- It is **weaker than a model would be** at picking good search terms. Accepted:
  a mediocre query that leaks nothing beats a good one that leaks. When a local
  reasoner is confirmed present, a `local-only` model could improve term
  selection without changing the egress story — recorded as a follow-up, not
  built.
- It **cannot be turned off**. There is no parameter, flag or configuration key
  that reaches the raw text. Principle 2 names a disable-able redaction as a
  violation *even when it defaults to on*.

## Constitution compliance

| Principle | Outcome | Why |
|---|---|---|
| 1. Brain plaintext under git | **Not implicated** | Research reads entry text and writes `tool_calls`; the brain is untouched. |
| 2. Privacy Airlock | **Governs, blocking** | A `local-only` run makes **zero** tool calls — not a redacted one, none — because a search carries the idea off the machine as surely as a completion does. Query construction is local on every profile. `redact()` has **no bypass parameter**; a test asserts its signature carries no flag, so adding one fails the build. The raw query is never stored, logged, or written to a payload. |
| 3. No empty mornings | **Constrains** | Quota exhaustion raises `ToolQuotaExceeded`, which the existing taxonomy already maps to `tool_quota`. The research stage fails; the night reaches `degraded` and the earlier stages still present. |
| 4. Text-first | **Not implicated** | No speech path. |
| 5. One codebase, two deployments | **Constrains** | Tavily specifics stay inside `providers/`. The judge instance has no credential and therefore makes no calls — the same code path, not a branch. |
| 6. Scope boundary | **Compliant** | Checked against both `NOT_BUILDING.md` tables. `search` and `extract` only; no crawl-at-large, no second provider, no summarization here (that is an agent's turn and a model call), and **nothing executes what it fetched**. |
| 7. Telemetry from line one | **Constrains** | Every tool call records the policy it ran under, its credits, its result count and its outcome. A cached result is marked `cached` and spends nothing. |

No violations.

## Non-goals

- No live search. There is no credential; nothing fabricates results.
- No caching layer beyond the `cached` flag.
- No second provider, no `crawl`, no summarization, no execution of fetched
  content.
- **No model-assisted query construction**, even locally. It is a real
  improvement and it is a different egress argument; recorded, not built.
