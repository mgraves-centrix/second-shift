// The morning, as data.
//
// Everything the screen does that could be wrong without anyone seeing lives
// here rather than in the page: which of three states a stage is in, what a
// missing reason is called, and the fact that an answer is always submitted
// against a decision id.
//
// In `.ts` rather than in the page because the web suite runs under
// `node --test`, which strips TypeScript types but does not transform JSX.
// Logic in a `.tsx` can only be asserted by reading the file's text, and a test
// that greps source passes the moment the symbol it names is renamed. This was
// learned in `frontend`, where the surface list had to be moved out of
// `Shell.tsx` for exactly that reason.

/** One stage of a night, as the briefing reports it. */
export interface StageLine {
  stage: string;
  status: string;
  /** Present for a failed stage, absent for a skipped one. See `stageReason`. */
  reason: string | null;
  artifacts: string[];
}

export interface NightLine {
  run_id: string;
  entry_id: string;
  night_of: string;
  outcome: string | null;
  effective_policy: string;
  stages: StageLine[];
}

export interface Question {
  decision_id: string;
  entry_id: string;
  question: string;
  /** Why the agent could not proceed. A question without one is a quiz. */
  rationale: string | null;
  blocking_stage: string | null;
  /**
   * Set by the API where the question was raised against a `local-only` entry —
   * the only questions whose answer could authorize sending the idea off the
   * machine. Read it, never re-derive it: the rule is the server's and a second
   * copy here is a second thing that can disagree.
   */
  will_leave_the_machine: boolean;
}

export interface Briefing {
  nights: NightLine[];
  questions: Question[];
  /** Set when the interviewer could not run. The nights above are still real. */
  interviewer_error: string | null;
}

/** The four ways a question can be disposed of. Not a backlog — outcomes. */
export const OUTCOMES = [
  { status: "decided", label: "Decided" },
  { status: "queued-for-tonight", label: "Queue for tonight" },
  { status: "deferred", label: "Defer" },
  { status: "obsolete", label: "Obsolete" },
] as const;

export type Outcome = (typeof OUTCOMES)[number]["status"];

/**
 * What a person reads on a marked question.
 *
 * Declared once, beside the rule, because the field name overstates it. The
 * server sets `will_leave_the_machine` for every question on a `local-only`
 * entry, which over-warns deliberately: answering *Defer* or *Obsolete* sends
 * nothing anywhere, and the narrower rule is not derivable because `decisions`
 * has no column separating "yes, take this one to the cloud" from any other
 * queued answer.
 *
 * So the sentence says what is true — that an answer here is the only thing
 * that could authorize it — rather than what the identifier suggests. A
 * component writing its own wording from the field's name is the failure the
 * demo label already had once.
 */
export const LEAVES_THE_MACHINE =
  "This idea is local-only. An answer here is the only thing that can " +
  "authorize sending it off the machine.";

/**
 * What an empty agenda says, which depends on whether there was a night.
 *
 * "The night got stuck on nothing it could not decide for itself" was rendered
 * on a morning with no night at all — the state you land in immediately after
 * an interview, because acting advances the delta boundary past the run you
 * just discussed. A sentence about a night is only true when there was one.
 *
 * Here rather than in the page so this is testable as behavior. The first
 * version of its test read the branch out of `page.tsx` and matched the comment
 * above the code, which is the failure mode this whole module exists to avoid.
 */
export function nothingWaiting(ranLastNight: boolean): string {
  return ranLastNight
    ? "Nothing is waiting on you — the night got stuck on nothing it could " +
        "not decide for itself."
    : "Nothing is waiting on you. You are up to date.";
}

/** Shown when a stage was skipped and the night recorded no reason. */
export const NO_REASON_RECORDED = "no reason recorded";

/**
 * What to print beside a stage.
 *
 * Three states, and the distinction between the last two is the load-bearing
 * one. `run_stages` has no reason column and the night persists only failures,
 * so a skipped stage reports *that* it was skipped and not *why*. Rendering
 * that as a blank would read as "no reason"; the truth is "not stored", and the
 * two are not the same claim.
 */
export function stageReason(stage: StageLine): string | null {
  if (stage.reason) return stage.reason;
  if (stage.status === "skipped") return NO_REASON_RECORDED;
  return null;
}

/**
 * What to print for an artifact, with the part that is already on screen removed.
 *
 * Artifacts are stored under `<night_of>/<run_id>/…`, so a six-stage night
 * renders the same 26-character ULID six times and the reader has to hunt for
 * the differing tail of each line. Rendering the full paths was measured — it
 * made the night's record three times taller than the interview on a phone,
 * which inverts the whole point of putting the questions first.
 *
 * A path that does not carry the expected prefix is returned whole. Guessing at
 * a shape we did not write is how a renderer starts lying about a file's
 * location.
 */
export function artifactLabel(path: string, night: NightLine): string {
  const prefix = `${night.night_of}/${night.run_id}/`;
  return path.startsWith(prefix) ? path.slice(prefix.length) : path;
}

/** Did this night produce anything at all? Principle 3's question, per run. */
export function completedStages(night: NightLine): StageLine[] {
  return night.stages.filter((s) => s.status === "complete");
}

export interface AnswerResult {
  decision_id: string;
  status: string;
  answered_at_ms: number;
}

/**
 * Answer one question the system asked.
 *
 * `decisionId` is the first positional parameter and there is no overload
 * without it. That is `NOT_BUILDING.md`'s excluded chat interface kept out
 * structurally rather than by convention: there is no way to call this with
 * text and no question, so there is no way for the screen to grow one.
 *
 * `modality` is passed explicitly rather than left to the server's default, so
 * the column that will carry `voice` has a caller supplying it today.
 */
export async function submitAnswer(
  decisionId: string,
  body: { answer: string; status: Outcome; modality?: "text" | "voice" },
  options: { apiBase?: string; signal?: AbortSignal } = {},
): Promise<AnswerResult> {
  const response = await fetch(
    `${options.apiBase ?? ""}/decisions/${encodeURIComponent(decisionId)}/answer`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        answer: body.answer,
        status: body.status,
        modality: body.modality ?? "text",
      }),
      signal: options.signal,
    },
  );
  if (!response.ok) {
    // Thrown rather than returned as a null result, because the caller must not
    // be able to advance the interview by ignoring it. An answer that did not
    // land is not an answer, and the night surface's "nothing was lost, this
    // view only reads" is false on this screen.
    throw new Error(`answer not recorded (${response.status})`);
  }
  return (await response.json()) as AnswerResult;
}
