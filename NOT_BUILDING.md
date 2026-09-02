# Not Building

The scope boundary is **idea in, artifact out, memory in between.**

Everything below was considered and deliberately excluded. This file exists so
that scope creep has to argue with a written record instead of with a mood.

## Override protocol

If a feature on this list gets requested later, the request is refused by
default. It ships only after an explicit, on-the-record override that names the
line being crossed and what is being cut to pay for it. Then it moves out of
this file and into the plan — this file is never silently edited.

---

## Excluded

| Feature | Why not |
|---|---|
| Calendar integration | Scheduling is not idea capture; it drags in OAuth, recurrence rules, and timezone edge cases that buy zero artifacts. |
| Email (reading, triage, sending) | An inbox is someone else's queue. This system works a queue you author deliberately. |
| Meeting attendance / recording / transcription | Meeting bots are a product category of their own, and the compliance surface (consent, retention, two-party states) is larger than the entire rest of this build. |
| Day planning / scheduling assistance | Telling you how to spend tomorrow is a different thesis from building something while you sleep. |
| Task management (todos, projects, boards) | `decisions` and `entries` already carry the only state the loop needs. A task system would become the product. |
| Open-mic wake-word listening | Multi-week always-listening pipeline with nothing demonstrable at the end. Push-to-talk is the whole feature at 2% of the cost. |
| Multi-user / accounts / sharing | Single-tenant by design. Auth, roles, and sharing semantics are pure overhead against a personal-AI thesis. |
| Mobile native app | The PWA installs, captures audio, and works offline-tolerant. A native build adds two app stores and a signing pipeline. |
| Third-party LLMs in the runtime path | Not a scope call — a rules call. The system must be evaluated on how it uses Nemotron and Nebius. |
| A general chat interface | The morning interview is structured and agenda-driven. An open chat box would quietly replace it and the product would become a worse ChatGPT. |
| Editing artifacts in-app | Artifacts land as files. Edit them in the tool that edits that kind of file. |
| Robotics or any physical-hardware loop | Considered and declined 27 Aug 2026. The Physical AI track was evaluated; Second Shift is a Personal AI track entry. Artifacts are files, not motion. |
| Autonomous execution of generated code | Generated builds are produced, not run unsupervised. Sandboxing an arbitrary code executor is a project, not a feature. |

---

## Deferred, not excluded

These are in scope but explicitly not now. Listed here so they stop being
re-litigated.

| Feature | When |
|---|---|
| TTS for the morning briefing | After text briefing works end to end. Verified on aarch64 2026-08-28; must still never block. |
| Celestial layer on the night scrubber | After the scrubber works. It is polish, and it is worth real time — but only once. |
| Vector search over the brain | ⚠️ **Shipped 2 Sep without meeting this condition — see below.** Original entry: only when keyword + recency retrieval demonstrably falls over. |

### ⚠️ Vector search over the brain — the condition was skipped, not met

`2026-09-02-add-retrieval` shipped exact cosine search over embeddings of
`entries` and brain topic files. It is running.

**The deferral condition was never evaluated, because it could not be.** It reads
"only when keyword + recency retrieval demonstrably falls over," and keyword +
recency retrieval was never built — there is no keyword search and no recency
ranking anywhere in `apps/api/secondshift/`, then or now. Nothing fell over.
The gate was stepped past rather than passed.

**The compliance check that should have caught it asserted the opposite.** The
proposal's constitution table, principle 6, reads *"Compliant — nothing in
`NOT_BUILDING.md`."* Vector search over the brain is in `NOT_BUILDING.md`, on
this page. The honest answer was "listed under *Deferred, not excluded*, with an
unmet condition," and writing that would have surfaced the question before the
code existed rather than a week after.

**What this is and is not.** It is not a constitution violation: principle 6
enumerates the *Excluded* table — calendar, email, meeting capture, day planning,
task management, wake words, multi-user, general chat — and vector search is on
the *Deferred* table, which says these are "in scope but explicitly not now." It
is not an override case either; the override protocol governs the Excluded list.
It is a deferral condition that was skipped, and a compliance claim that was
false.

**The entry stays here until decided.** Two things are open and both are the
subject's call:

1. Build keyword + recency retrieval as the baseline the condition names, and
   measure whether cosine actually beats it on this corpus — or accept that the
   comparison will never be run and say so.
2. Move this entry out of the file, per the protocol, once (1) is answered.

Recommendation: do (1). The condition was written because a 600-entry corpus is
small enough that recency plus keyword may well win, and cosine over six
documents has never been compared against anything. It is a day's work and it is
the only way the claim "vector search earns its place here" becomes something
other than an assumption. Until then this entry is the record that it is one.
