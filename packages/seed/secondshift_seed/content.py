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
