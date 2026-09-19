"""The words a generated night is made of.

Structure is faithful; content admits what it is. Every string here is prefixed
or named so that a person reading a seeded night on screen can tell in one
glance that nobody thought it — imitating someone's real captured thinking
would make a demo that lies about whose ideas it is showing, and the structure
is the part the scrubber needs.

Kept apart from `night` so the shape of a night and the words in it can be
revised independently. The judge deployment's persona rewrites this module and
nothing else.
"""

from __future__ import annotations

SYNTHETIC = "[synthetic]"

#: Captured ideas, as (title, spoken or typed body). Titles are short because
#: the capture surface derives one at that length from real text.
IDEAS: tuple[tuple[str, str], ...] = (
    (
        f"{SYNTHETIC} nightly digest",
        f"{SYNTHETIC} A digest that reads the week's captured notes overnight "
        "and returns the single decision worth making tomorrow.",
    ),
    (
        f"{SYNTHETIC} scrubber shortcuts",
        f"{SYNTHETIC} Keyboard control for the night scrubber, so a long run "
        "can be reviewed without ever reaching for the mouse.",
    ),
    (
        f"{SYNTHETIC} offline capture queue",
        f"{SYNTHETIC} Capture should survive an airplane. Queue locally, drain "
        "on reconnect, and keep the original capture instant.",
    ),
    (
        f"{SYNTHETIC} failure ledger digest",
        f"{SYNTHETIC} A weekly read of the failure ledger that says which "
        "problem is recurring rather than which one was loudest.",
    ),
    (
        f"{SYNTHETIC} morning brief pacing",
        f"{SYNTHETIC} The morning brief opens with the question the night got "
        "stuck on, not with a summary of what succeeded.",
    ),
    (
        f"{SYNTHETIC} variant comparison view",
        f"{SYNTHETIC} Show three mockup variants side by side with the "
        "critic's ranking and the one sentence that decided it.",
    ),
    (
        f"{SYNTHETIC} policy at a glance",
        f"{SYNTHETIC} Every screen that shows an idea should show the policy "
        "it runs under, without anyone having to open a menu.",
    ),
    (
        f"{SYNTHETIC} cost curve per idea",
        f"{SYNTHETIC} Spend charted per accepted artifact rather than per "
        "night, so a cheap night that produced nothing reads as expensive.",
    ),
    (
        f"{SYNTHETIC} voice answer for the interview",
        f"{SYNTHETIC} Answering a morning question by speaking should land in "
        "the same place typing does, with no separate path.",
    ),
    (
        f"{SYNTHETIC} retention classes for payloads",
        f"{SYNTHETIC} Mark a payload ephemeral at capture time so an idea can "
        "be reasoned about without being kept.",
    ),
)

#: Search subjects, already reduced to the redacted form a tool call stores.
#: The raw query is never written for a real entry and is not written here.
TOPICS: tuple[str, ...] = (
    "offline-first sync patterns",
    "timeline rendering at ten thousand rows",
    "prompt versioning in agent systems",
    "critic rubrics for generated interfaces",
    "append-only schemas in SQLite",
    "local inference throughput on small accelerators",
    "redaction before egress",
    "checkpointed pipelines and partial results",
)

#: What each stage's work reads as in a label, one clause long. The scrubber
#: renders these directly; anything that needs a second line is too long.
STAGE_WORK: dict[str, tuple[str, ...]] = {
    "brief": (
        "framing the captured idea",
        "listing what is not yet decided",
        "drafting the question to ask in the morning",
    ),
    "research": (
        "gathering prior art",
        "extracting the two claims that matter",
        "discarding a source that repeated itself",
    ),
    "mockups": (
        "sketching a layout variant",
        "laying out the dense case",
        "checking the variant against the brief",
    ),
    "build": (
        "assembling the variant",
        "wiring the timeline query",
        "compiling and checking the result",
    ),
    "critique": (
        "ranking the variants",
        "naming why the runner-up lost",
        "rejecting a variant that ignored the brief",
    ),
    "distill": (
        "reducing the night to one page",
        "carrying the open question forward",
        "writing tomorrow's starting point",
    ),
}

#: Resolutions recorded against generated failures. Phrased as an action taken,
#: which is what the ledger's `latest_resolution` column is read for.
RESOLUTIONS: tuple[str, ...] = (
    "retried on the local reasoner at a shorter context",
    "reduced the batch until it fit in memory",
    "skipped the source and continued with the remaining two",
    "pinned the dependency and rebuilt",
)


def output_path(stage: str, slug: str) -> str:
    """Where a generated file claims to live.

    Under a `synthetic/` root so a directory listing separates seeded output
    from real output without anyone having to consult the database.
    """
    return f"synthetic/{stage}/{slug}.md"


#: What the interviewer asks after a night, as (question, rationale) pairs.
#:
#: Written as an agent that tried something and stopped, because the rationale
#: is what separates a question from a quiz — `morning-interview`'s own rule.
#: A seeded night raised none of these until 19 Sep, so the judge deployment
#: rendered "Nothing is waiting on you" on the screen the product is named for.
DECISIONS: tuple[tuple[str, str], ...] = (
    (
        f"{SYNTHETIC} Should a note that spans two topics be filed under both, "
        "or under the one it is mostly about?",
        "I built the grouping and both readings produce a coherent digest. They "
        "diverge on the notes that matter most — the ones written while thinking "
        "across two things at once. Duplicating makes the week look busier than "
        "it was; picking one loses the connection. I could not choose without "
        "knowing which failure you would rather read.",
    ),
    (
        f"{SYNTHETIC} The critic ranked the third build above the first. Keep "
        "its ranking, or the order they were generated in?",
        "The critic's note says the third handles an empty week and the first "
        "does not, which is the case you described. But it scored lower on "
        "everything else, so promoting it trades the common case for the edge "
        "one. That is a judgment about what you will actually open.",
    ),
    (
        f"{SYNTHETIC} May I search the web for how other people schedule a "
        "weekly review?",
        "The brief asserts Sunday evening and the brain holds nothing about "
        "your week. I stopped rather than build a schedule on an assumption I "
        "invented. Searching means the topic of this idea leaves the machine.",
    ),
)


#: The bodies a seeded night's artifacts carry.
#:
#: Real bytes, because the seeder wrote rows with none behind them and said so
#: in its own docstring — which was fine while nothing served artifacts, and
#: became a demo offering files that 404 the moment something did.
ARTIFACT_BODIES: dict[str, str] = {
    "brief": (
        "# {title}\n\n"
        "{text}\n\n"
        "## What is settled\n\n"
        "A single page per week, generated overnight, grouped by subject rather "
        "than by the day a note was captured.\n\n"
        "## What is not\n\n"
        "Whether a note spanning two subjects is duplicated or assigned to one. "
        "Raised as a question rather than decided here.\n"
    ),
    "research_digest": (
        "# Research digest\n\n"
        "Three sources, two of which agree. The redacted query was the only "
        "thing that left the machine; what came back is summarized here and the "
        "tool call holds the query, not the idea.\n\n"
        "- Weekly reviews cluster on Sunday evening and Monday morning.\n"
        "- Grouping by subject beats grouping by day once a week exceeds "
        "roughly twenty notes.\n"
        "- One source repeated another and was discarded.\n"
    ),
    "mockup": (
        "# Layout\n\n"
        "One column. The week's decision at the top, the notes that produced it "
        "underneath, grouped by subject with the subject as a heading.\n\n"
        "Rejected: a two-column layout. It reads well at a desk and badly on "
        "the phone, which is where this is actually opened.\n"
    ),
    "build": (
        "# Build variant {index}\n\n"
        "Generates the page from the week's entries.\n\n"
        "- Handles an empty week by saying so rather than rendering a blank "
        "page.\n"
        "- Groups by subject, falling back to capture order where no subject "
        "is derivable.\n"
        "- Ranked {rank} of {total} by the critic.\n"
    ),
    "critique": (
        "# Critique\n\n"
        "The variants differ on one thing that matters: what an empty week "
        "renders.\n\n"
        "Ranked by whether the page is readable when the week was quiet, then "
        "by how little the grouping has to guess. The ranking is the critic's "
        "and is recorded as such — it is not the order they were built in.\n"
    ),
    "summary": (
        "# What the night did\n\n"
        "Framed the idea, gathered prior art, drew a layout, built variants and "
        "ranked them.\n\n"
        "One question is waiting: whether a note spanning two subjects is "
        "duplicated or assigned. Everything downstream of that answer is built "
        "and none of it is committed to.\n"
    ),
}
