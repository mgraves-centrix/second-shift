"""Building a search query that carries no idea with it.

**This is construction, not filtering, and the difference is the whole design.**

The obvious shape is `redact(entry_text) -> safe_text` and then search that. It
fails open. A filter has to recognize everything dangerous, so an unknown proper
noun passes, a codename that looks like a common word passes, and — the category
no filter can address at all — the subject's own phrasing passes. Six distinctive
words are enough to identify who wrote something, and none of them need to be a
name.

So the raw text is never a candidate to become a query. A token has to *earn its
way in*: it must be lowercase in the source (or sentence-initial), not a
stopword, not credential-shaped, and long enough to be a topic rather than
grammar. An unrecognized codename is dropped for being capitalized, not for
being on a list, which is what makes this fail closed.

**The cost, stated rather than hidden:** dropping every capitalized token loses
real search terms. "Rust", "Kubernetes" and "SQLite" go too. Queries are worse
than a person would write, and that is the accepted trade — a mediocre query
that leaks nothing beats a good one that leaks.

**There is no bypass and there is no second parameter.** Constitution principle 2
names a redaction that configuration can disable as a violation *even when it
defaults to on*, so the guard is not a safe default but the absence of anywhere
to put an unsafe one. `test_research.py` inspects this signature and fails the
build if it grows an argument.
"""

from __future__ import annotations

import re

#: Grammar and framing words. Deliberately short: this list exists to stop the
#: query being mostly filler, not to be a linguistic resource. Anything it
#: misses is a worse query, never a leak — the capitalization rule is what
#: carries the safety property.
_STOPWORDS = frozenset(
    """
    a about after all also am an and any are as at be because been before being
    but by can could did do does doing down each few for from further had has
    have having he her here hers him his how i if in into is it its just me more
    most my no nor not now of off on once only or other our out over own same
    she should so some such than that the their them then there these they this
    those through to too under until up very was we were what when where which
    while who whom why will with would you your
    something someone thing things stuff way ways need needs want wants
    everything everyone anything anyone nothing nobody people person
    either neither both else again ever never always sometimes often
    get gets got make makes made take takes took keep keeps kept
    out out-of into onto upto really quite rather still yet even much many
    """.split()
)

#: A token that is mostly not-a-word — long, mixed case, digits or symbols. The
#: shape of an API key, a token, a hash or a path. Refused outright: this is the
#: one category where the right answer is that nothing about it is searchable.
_CREDENTIAL_SHAPED = re.compile(r"^(?=.*\d)[\w\-./+=]{16,}$|^[\w\-]*(?:key|token|secret|pw|pass)[\w\-]*[-_=][\w\-]{8,}$", re.I)

#: Anything with an `@`, a scheme, or a dotted host. Addresses and locations
#: never become search terms. Trailing punctuation is stripped before this is
#: applied — a private hostname at the end of a sentence leaked past an earlier
#: version of this pattern, which anchored on `$` and so never matched the span
#: while it still carried a trailing period.
_CONTACT_SHAPED = re.compile(r"@|^https?://|^[\w-]+(?:\.[\w-]+){1,}$", re.I)

#: Topics where a lowercase common word is itself the disclosure. This is the
#: one place the module filters rather than constructs, and **it fails open** —
#: a term not listed here passes. It is a backstop, not the mechanism.
#:
#: The capitalization rule cannot reach this category: "chemo", "divorce" and
#: "redundancy" are lowercase, ordinary, and none of them are proper nouns. An
#: earlier version of this module shipped without it and let
#: "managing standups around chemo schedule" through, which is exactly the
#: leak-list category 5 names. Listed by topic rather than exhaustively,
#: because an exhaustive list of what a person might not want searched does not
#: exist — see the spec's note on what this does not cover.
_SENSITIVE = frozenset(
    """
    chemo chemotherapy cancer diagnosis diagnosed therapy therapist psychiatrist
    depression anxiety medication prescription surgery hospital clinic illness
    divorce custody lawyer attorney lawsuit litigation settlement deposition
    salary compensation equity vesting severance redundancy layoff fired
    resignation bankruptcy debt mortgage foreclosure
    visa immigration deportation asylum
    pregnant pregnancy miscarriage fertility
    """.split()
)

#: Word characters plus internal hyphens and apostrophes. Splitting on this
#: rather than on whitespace means punctuation never rides along into a query.
_TOKEN = re.compile(r"[A-Za-z][A-Za-z'\-]*[A-Za-z]|[A-Za-z]")

#: Terms in a query. Past roughly this many, a search engine's results stop
#: improving and the query starts being a fingerprint of the sentence it came
#: from — which is category 8 arriving by a different door.
MAX_TERMS = 8

#: Below this, a token is grammar rather than a topic.
_MIN_LENGTH = 3


def _sentence_initial_positions(text: str) -> set[int]:
    """Word indices that begin a sentence.

    A capital there is punctuation, not a proper noun, so it must not be the
    reason a legitimate topic word is dropped. Without this, the first word of
    every entry is discarded — including the one that is usually the subject.
    """
    positions: set[int] = set()
    index = 0
    start_of_sentence = True
    for match in re.finditer(r"[A-Za-z][A-Za-z'\-]*|[.!?\n]", text):
        token = match.group()
        if token in ".!?\n":
            start_of_sentence = True
            continue
        if start_of_sentence:
            positions.add(index)
            start_of_sentence = False
        index += 1
    return positions


def build_query(text: str) -> str:
    """The searchable question inside an idea, carrying nothing that identifies it.

    Takes the source text and nothing else. There is deliberately no second
    parameter — see this module's docstring for why that is the mechanism rather
    than a style choice.
    """
    initial = _sentence_initial_positions(text)
    terms: list[str] = []
    seen: set[str] = set()

    for index, match in enumerate(_TOKEN.finditer(text)):
        raw = match.group()

        # A capital that does not begin a sentence is a name, an organization, a
        # product or a codename. Dropped without asking which — that is what
        # makes an unknown one as safe as a known one.
        if raw[0].isupper() and index not in initial:
            continue

        lowered = raw.lower()
        if lowered in _STOPWORDS or len(lowered) < _MIN_LENGTH:
            continue
        if lowered in _SENSITIVE:
            continue
        if lowered in seen:
            continue

        # Checked against the surrounding source token, not the word-only match,
        # so a key's digits and symbols are still visible to the pattern.
        surrounding = _surrounding_token(text, match.start())
        if _CREDENTIAL_SHAPED.match(surrounding) or _CONTACT_SHAPED.search(surrounding):
            continue

        seen.add(lowered)
        terms.append(lowered)
        if len(terms) == MAX_TERMS:
            break

    # Order is a safety property here, not tidiness. Keeping source order left
    # the query as the sentence with a few words removed:
    # "How does Contoso handle on-call rotations without burning people out?"
    # became "handle on-call rotations without burning people" — six consecutive
    # words, no names, and a fingerprint of the writer's phrasing. That is
    # leak-list category 8 arriving through a door the capitalization rule does
    # not watch.
    #
    # Sorting alone does *not* fix it, which an earlier version of this comment
    # claimed. Where the source words already run in alphabetical order, the
    # sorted query reproduces them verbatim — `burning handle on-call rotations
    # without` still carried a four-word run. So the order is verified against
    # the source and repaired, rather than assumed safe because it was shuffled.
    return " ".join(_break_runs(sorted(terms), text))


#: Consecutive source words that may not appear in a query. Three is a phrase;
#: two is a collocation that any search on the topic would produce anyway.
_MAX_RUN = 3


def _break_runs(terms: list[str], source: str) -> list[str]:
    """Reorder until the query reproduces no run of the source. Deterministic.

    Sorting decorrelates the query from the sentence *usually*, and usually is
    not the standard for the one function standing between a private idea and a
    third party. This checks the property and repairs it, so the guarantee comes
    from a verified postcondition rather than from an argument about shuffling.

    Rotation is the repair: it preserves the term set exactly — nothing is lost
    and nothing new is introduced — and each rotation breaks a different
    adjacency. If no rotation is clean, the query gives up a term rather than
    ship a run; the caller's `_MIN_TERMS` floor then decides whether what is
    left is still worth searching.
    """
    words = [w for w in re.findall(r"[a-z'\-]+", source.lower())]
    runs = {
        " ".join(words[i : i + _MAX_RUN]) for i in range(max(0, len(words) - _MAX_RUN + 1))
    }

    def clean(candidate: list[str]) -> bool:
        joined = " ".join(candidate)
        return not any(run in joined for run in runs)

    for offset in range(len(terms)):
        rotated = terms[offset:] + terms[:offset]
        if clean(rotated):
            return rotated

    # No rotation was clean. Drop the last term and try again — a shorter query
    # that carries no phrase beats a complete one that does.
    return _break_runs(terms[:-1], source) if len(terms) > 1 else terms


def _surrounding_token(text: str, at: int) -> str:
    """The whitespace-delimited token containing this position.

    `_TOKEN` matches letters only, so `sk-live-9f2b...` reaches the loop as
    `sk`. Credential and contact shapes live in the digits and symbols that
    match strips, so they have to be judged against the original span.
    """
    start = text.rfind(" ", 0, at) + 1
    end = text.find(" ", at)
    span = text[start : end if end != -1 else len(text)].strip()
    # Trailing sentence punctuation, stripped before the shape patterns run.
    # `_CONTACT_SHAPED` anchors on `$`, so a host at the end of a sentence
    # arrived with its trailing period still attached and did not match — the
    # private hostname then reached the query one token at a time.
    return span.rstrip(".,;:!?)\"'")
