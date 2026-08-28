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
| Vector search over the brain | Only when keyword + recency retrieval demonstrably falls over. |
