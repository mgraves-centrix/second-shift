# Eval prompt candidates

Ten candidates. **Five get selected** and become the held-out set — run weekly,
scored against a fixed rubric, never used during development. The other five stay
here as reserves.

## What makes an eval prompt good here

The product claim is that it *interrogates an idea before spending compute on
it*. So a prompt with no hidden ambiguity measures nothing — the system would
look identical in week 1 and week 8.

Every candidate below has at least one of:

- **buried ambiguity** a good interviewer surfaces and a bad one assumes past
- **a hidden bad assumption** worth challenging rather than building on
- **an answer that depends on knowing you** — so it improves as the profile does
- **a scope trap** that should be narrowed or refused

They are also all things you might plausibly capture, because an eval set that
does not look like real usage measures the wrong thing.

## Selection guidance

Take five that span the categories, not the five you like most. Suggested shape:
one vague, one trap, one research-dependent, one taste-dependent, one technical.

Mark your picks and I will fix them, hash the rubric, and record the day-3
baseline.

---

### 1. Vague by design — tests interrogation directly {#repeat-mistake}

> "Something that helps me notice when I'm about to repeat a mistake I've
> already made once."

Almost nothing is specified: notice where, from what signal, at what moment,
with what interruption cost. A naive system builds a generic reminder. A learned
one asks whether this means the failure ledger, code review, or something about
how you spend a weekend.

### 2. The trap — should be pushed back on, not built {#every-metric-dashboard}

> "A dashboard showing every metric about my projects in one place."

This is the idea that always sounds good and almost never gets used. A system
that has learned anything should ask which decision the dashboard would change,
and probably argue for one number instead of forty. If it cheerfully builds a
dashboard, it has learned nothing.

### 3. Depends on knowing you — tests the profile {#readme-in-my-voice}

> "Draft the README for whatever I'm working on right now, in my voice."

Week 1 it cannot know your voice and should say so. Week 8 the style guide has
been revised against real accepted and rejected artifacts. This is the most
direct measure of the profile improving, and the easiest to score honestly.

### 4. Research-dependent — tests Tavily and synthesis {#agent-memory-systems}

> "What are people doing about the fact that agent memory systems all seem to
> either forget everything or remember too much?"

Requires actual search, and the quality difference is stark: a naive answer lists
tools, a good one identifies the axis they differ on and where the real
disagreement is.

### 5. Scope boundary — should be narrowed, not refused outright {#small-follow-ups}

> "Help me stop losing track of the small follow-ups that come out of
> conversations."

This is task management with a nicer name — `NOT_BUILDING.md` excludes it. But
refusing flatly is wrong too: capturing a follow-up *as an idea* is exactly what
the product does. Tests whether the boundary is understood or merely enforced.

### 6. Technical with a genuine trade-off {#cheaper-nights}

> "I want the night runs to cost less without getting worse. Where's the
> waste?"

There is a real answer (batch pricing, prompt caching, escalation policy,
completion-heavy stages) and a lazy one (use a smaller model). Improves sharply
once telemetry has weeks of real data — which makes it a good measure of the
system using its own instrumentation.

### 7. Deliberately small — tests proportionality {#file-naming}

> "A better way to name the files this thing produces."

Small, real, and a trap for over-engineering. A system that returns a taxonomy
with a migration plan has failed. One that proposes a convention and moves on
has understood the scale.

### 8. Personal workflow — tests observation over assumption {#context-switching}

> "I keep context-switching between the Spark and my laptop and losing my place.
> Fix that."

The right answer depends on what actually happens, which the system can only
know by having watched. Week 1 gives generic tooling advice; week 8 should cite
something it has observed about how the two machines get used.

### 9. Ambiguous scope, two readings — tests clarifying over guessing {#shorter-briefing}

> "Make the morning briefing shorter."

Shorter how — fewer items, less detail per item, or a tighter voice? Those are
three different products. A good interviewer asks. A bad one picks and is right
a third of the time.

### 10. Long-horizon judgement — tests memory over recall {#been-avoiding}

> "What have I been avoiding?"

Answerable only from accumulated evidence: ideas captured and never run,
decisions deferred repeatedly, artifacts opened once and abandoned. Week 1 has
nothing to say and should admit it. Week 8 should be uncomfortable to read.

---

## Notes on scoring

Two of these — 3 and 10 — should produce an **honest "I don't know yet"** in
week 1. Score that as *correct*, not as failure. A system that fabricates a
confident answer in week 1 and a confident answer in week 8 shows no
improvement; one that starts by admitting the gap and ends by filling it shows
exactly the thing being claimed.
