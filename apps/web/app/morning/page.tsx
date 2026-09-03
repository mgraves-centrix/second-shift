"use client";

// The interview.
//
// One question at a time, with the agenda's length visible. A list of questions
// each with a box under it is a form, and a form gets answered easy-first — the
// night's actual blocker is rarely the easy one. Every outcome advances,
// including *Defer*, which is what makes deferring first-class in the screen
// and not only in the schema.
//
// It is also the anti-chat argument in layout. `NOT_BUILDING.md` excludes a
// general chat interface by name. With one agenda item on screen, whose text
// box is rendered inside a specific question and whose submit path carries that
// question's decision id, there is nowhere to put an instruction that is not an
// answer to something the system asked.
//
// No microphone. ADR 0006 binds an end-of-utterance detector that has never
// been run, and a waveform with no transcription behind it is decoration on the
// one screen that is the product. Principle 4 is satisfied by text being the
// only path rather than despite it — and this file references no speech API at
// all, which a test asserts by name.

import { useCallback, useEffect, useState } from "react";

import { Nav } from "@/components/shell/Shell";
import {
  LEAVES_THE_MACHINE,
  OUTCOMES,
  artifactLabel,
  nothingWaiting,
  type Briefing,
  type NightLine,
  type Outcome,
  type Question,
  stageReason,
  submitAnswer,
} from "@/lib/morning";
import styles from "./morning.module.css";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

type Status = "loading" | "ready" | "unreachable";

export default function MorningPage() {
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [index, setIndex] = useState(0);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE}/morning`, { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((body: Briefing | null) => {
        if (!body) {
          setStatus("unreachable");
          return;
        }
        setBriefing(body);
        setStatus("ready");
      })
      .catch(() => {
        /* Aborted by unmount, or the API went away. */
      });
    return () => controller.abort();
  }, []);

  const questions = briefing?.questions ?? [];
  const current: Question | undefined = questions[index];

  const dispose = useCallback(
    async (outcome: Outcome) => {
      if (!current || sending) return;
      setSending(true);
      setFailed(null);
      try {
        await submitAnswer(
          current.decision_id,
          { answer: draft, status: outcome, modality: "text" },
          { apiBase: API_BASE },
        );
        // Advance only on a recorded answer. The draft is cleared here and
        // nowhere else, so a failure keeps what was typed.
        setDraft("");
        setIndex((i) => i + 1);
      } catch {
        setFailed(
          "That answer was not recorded — the orchestrator did not accept it. " +
            "What you typed is still here.",
        );
      } finally {
        setSending(false);
      }
    },
    [current, draft, sending],
  );

  return (
    <>
      <Nav />
      <main className={styles.page}>
        {status === "unreachable" ? (
          <p className={styles.notice}>
            The orchestrator is not answering, so there is no briefing to show.
            Nothing has been lost; nothing has been recorded either.
          </p>
        ) : null}

        {status === "loading" ? (
          <p className={styles.notice}>Reading last night…</p>
        ) : null}

        {briefing ? (
          <>
            <Interview
              questions={questions}
              index={index}
              draft={draft}
              onDraft={setDraft}
              onDispose={dispose}
              sending={sending}
              failed={failed}
              interviewerError={briefing.interviewer_error}
              ranLastNight={briefing.nights.length > 0}
            />
            <Record nights={briefing.nights} />
          </>
        ) : null}
      </main>
    </>
  );
}

/**
 * The agenda, one item at a time.
 *
 * `index` past the end is the finished state rather than an empty question —
 * an interview that runs out of questions has ended, and saying so is not the
 * same as rendering nothing.
 */
function Interview({
  questions,
  index,
  draft,
  onDraft,
  onDispose,
  sending,
  failed,
  interviewerError,
  ranLastNight,
}: {
  questions: Question[];
  index: number;
  draft: string;
  onDraft: (value: string) => void;
  onDispose: (outcome: Outcome) => void;
  sending: boolean;
  failed: string | null;
  interviewerError: string | null;
  ranLastNight: boolean;
}) {
  if (interviewerError) {
    // Principle 3: beside the facts, never instead of them. `Record` renders
    // below this whatever happens here.
    return (
      <section className={styles.interview}>
        <p className={styles.notice}>
          The interviewer could not run, so there are no questions this morning.
          What the night produced is below. ({interviewerError})
        </p>
      </section>
    );
  }

  if (questions.length === 0) {
    return (
      <section className={styles.interview}>
        <p className={styles.notice}>{nothingWaiting(ranLastNight)}</p>
      </section>
    );
  }

  const current = questions[index];
  if (!current) {
    return (
      <section className={styles.interview}>
        <p className={styles.done}>
          That is everything — {questions.length}{" "}
          {questions.length === 1 ? "question" : "questions"} answered. Tonight
          picks up what you queued.
        </p>
      </section>
    );
  }

  return (
    <section className={styles.interview} aria-label="Interview">
      <header className={styles.agenda}>
        <span className={styles.count}>
          {index + 1} of {questions.length}
        </span>
        <span className={styles.dots} aria-hidden="true">
          {questions.map((q, i) => (
            <span
              key={q.decision_id}
              className={styles.dot}
              data-state={i < index ? "done" : i === index ? "current" : "todo"}
            />
          ))}
        </span>
      </header>

      <h1 className={styles.question}>{current.question}</h1>
      {current.rationale ? (
        <p className={styles.rationale}>{current.rationale}</p>
      ) : null}
      {current.will_leave_the_machine ? (
        <p className={styles.egress} role="note">
          {LEAVES_THE_MACHINE}
        </p>
      ) : null}

      <label className={styles.field}>
        <span className={styles.label}>Your answer</span>
        <textarea
          className={styles.input}
          value={draft}
          onChange={(e) => onDraft(e.target.value)}
          rows={4}
          /* Bound to this question and re-created when it changes, so a draft
           * cannot be carried onto a question it was not written for. */
          key={current.decision_id}
        />
      </label>

      {failed ? <p className={styles.failed}>{failed}</p> : null}

      <div className={styles.outcomes}>
        {OUTCOMES.map((outcome) => (
          <button
            key={outcome.status}
            type="button"
            className={styles.outcome}
            data-outcome={outcome.status}
            disabled={sending}
            onClick={() => onDispose(outcome.status)}
          >
            {outcome.label}
          </button>
        ))}
      </div>
    </section>
  );
}

/** What the night did, under the agenda: context for the answer that needs it. */
function Record({ nights }: { nights: NightLine[] }) {
  if (nights.length === 0) {
    return (
      <section className={styles.record}>
        <p className={styles.notice}>
          Nothing has run since your last answer.
        </p>
      </section>
    );
  }
  return (
    <section className={styles.record}>
      <h2 className={styles.recordHeading}>What the night did</h2>
      {nights.map((night) => (
        <article key={night.run_id} className={styles.night}>
          <h3 className={styles.nightOf}>
            {night.night_of}
            <span className={styles.policy}>{night.effective_policy}</span>
          </h3>
          <ul className={styles.stages}>
            {night.stages.map((stage) => {
              const reason = stageReason(stage);
              return (
                <li key={stage.stage} className={styles.stage}>
                  <span className={styles.stageName}>{stage.stage}</span>
                  <span
                    className={styles.stageStatus}
                    data-status={stage.status}
                  >
                    {stage.status}
                  </span>
                  <span className={styles.stageDetail}>
                    {stage.artifacts.length > 0
                      ? stage.artifacts
                          .map((a) => artifactLabel(a, night))
                          .join(", ")
                      : reason}
                  </span>
                </li>
              );
            })}
          </ul>
        </article>
      ))}
    </section>
  );
}
