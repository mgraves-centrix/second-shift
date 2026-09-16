"""Building a search query that carries no idea with it.

**This is construction, not filtering, and the difference is the whole design.**

The obvious shape is `redact(entry_text) -> safe_text` and then search that. It
fails open. A filter has to recognize everything dangerous, so an unknown proper
noun passes, a codename that looks like a common word passes, and — the category
no filter can address at all — the subject's own phrasing passes. Six distinctive
words are enough to identify who wrote something, and none of them need to be a
name.

So the raw text is never a candidate to become a query. A token has to *earn its
way in*: it must be lowercase in the source (or an ordinary word opening a
sentence), not a stopword, not shaped like a credential, address or
identifier, and long enough to be a topic rather than grammar. An unrecognized
codename is dropped for being capitalized, not for being on a list, which is
what makes this fail closed.

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
_CREDENTIAL_SHAPED = re.compile(r"^(?=.*\d)[\w\-./+=]{16,}$|^[\w\-]*(?:key|token|secret|pw|pass)[\w\-]*[-_=:][\w\-]{8,}$", re.I)

#: Anything with an `@`, a scheme, or a dotted host, with or without a port or a
#: path. Addresses and locations never become search terms. Surrounding
#: punctuation is stripped before this is applied — a private hostname at the
#: end of a sentence leaked past an earlier version of this pattern, which
#: anchored on `$` and so never matched the span while it still carried a
#: trailing period, and `spark-box.lan:8000` leaked because the port did too.
_CONTACT_SHAPED = re.compile(
    r"@|^[a-z][a-z0-9+.\-]*://|^[\w-]+(?:\.[\w-]+)+(?::\d+)?(?:/\S*)?$|^[\w-]+:\d+$",
    re.I,
)

#: A span that is an identifier rather than a word. Any of:
#:
#: - a digit or an underscore;
#: - a path or assignment character (`/`, `\\`, `=`), because a path carries a
#:   username or a host segment and an assignment carries a value, and neither
#:   is ever a topic — `/srv/jdoe/...`, `\\\\nas-box\\media` and `host=nas-box`
#:   all leaked one segment at a time;
#: - a lowercase letter followed by an uppercase one, which vocabulary does not
#:   do and generated keys routinely do;
#: - a hyphenated run too long to be vocabulary.
#:
#: The credential pattern above needs a digit or a key-like prefix and misses a
#: key made only of letters; this does not ask what the span is for.
_IDENTIFIER_SHAPED = re.compile(r"[\d_/\\=]|[a-z][A-Z]|^[A-Za-z-]{20,}$")

#: Ordinary words an entry opens with. A capital at the start of a sentence is
#: punctuation *or* a name, and nothing in the text says which — "Build a
#: pipeline" and "Contoso wants a pipeline" have the same shape. So an opening
#: capital earns its way in only by being one of these; an unlisted one is
#: dropped as a name would be.
#:
#: This is the module's rule applied to the one position it had exempted.
#: Treating every sentence-initial capital as punctuation let a name that
#: opened an entry through, and let any capital after a period through — "Dr.
#: Okonkwo" ends a sentence as far as punctuation can tell. It fails closed: a
#: good opening word missing from this list costs a search term, never a leak.
_OPENERS = frozenset(
    """
    add adapt allow analyze automate avoid build bundle cache change check
    choose clean collect combine compare compute consider convert count create
    cut debug decide define deploy design detect draft estimate evaluate explain
    explore export figure find finish fix follow generate group handle help
    idea ideas improve import index investigate keep learn list load look make
    managing map measure merge migrate model monitor move need notes plan
    prototype publish reduce refactor remove rename render replace report
    research review rewrite run schedule score search send set ship show
    simplify sketch sort split start stop store stream summarize support
    sync test track train try turn update upgrade use validate write
    how what why when where which who should could would can does is are
    maybe perhaps possibly probably
    """.split()
)

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

    A capital there may be punctuation rather than a proper noun, and the
    opening word is usually the subject. It is still only a candidate: see
    `_OPENERS` for what it must also be before it is kept.
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

        # A capital is a name, an organization, a product or a codename, and is
        # dropped without asking which — that is what makes an unknown one as
        # safe as a known one. At the start of a sentence it may be punctuation
        # instead, and it is kept only where it is an ordinary opening word.
        if raw[0].isupper() and not (index in initial and raw.lower() in _OPENERS):
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
        if (
            _CREDENTIAL_SHAPED.match(surrounding)
            or _CONTACT_SHAPED.search(surrounding)
            or _IDENTIFIER_SHAPED.search(surrounding)
        ):
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

    Delimited by any whitespace. An earlier version looked only for a space, so
    a host after a newline or a key before a tab was judged as part of a larger
    span that matched no shape, and reached the query one label at a time.
    """
    start = at
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    end = at
    while end < len(text) and not text[end].isspace():
        end += 1
    # Surrounding punctuation, stripped before the shape patterns run. The
    # patterns anchor on both ends, so a host in parentheses or at the end of a
    # sentence arrived with its punctuation attached and matched nothing.
    return text[start:end].strip(".,;:!?()[]{}<>\"'`")
