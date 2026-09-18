"""The in-memory index, and assembly over it.

Brute-force cosine over a `numpy` array, per ADR 0002. At the corpus this
system produces — 6 documents on 2 Sep, roughly 600 entries projected by week
eight — exact search over an in-memory array is instant and, unlike an
approximate index, correct. ADR 0002's own instruction stands: revisit when
retrieval demonstrably falls over, not on principle.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..brain.repo import BrainRepo, BrainUnavailable
from ..db.repository import Repository
from ..providers.base import Embedder

#: Policies a document can carry, most restrictive first. A document may be
#: assembled for a run whose policy is at or below its own restriction.
LOCAL_ONLY = "local-only"
CLOUD_ASSISTED = "cloud-assisted"

#: Brain content is `local-only` until somebody decides otherwise on the record.
#: The brain is derived from every idea regardless of the policy each was
#: captured under, so the safe reading of "only assembled, policy-filtered
#: context is ever eligible to leave" is that a file distilled from local-only
#: material inherits local-only. Failing closed costs a cloud-assisted run its
#: brain context; failing open would leak the memory the airlock exists to
#: protect, and only one of those is recoverable.
BRAIN_POLICY = LOCAL_ONLY


@dataclass(frozen=True, slots=True)
class Document:
    """One indexable unit of what the system knows."""

    source: str
    text: str
    policy: str


@dataclass(frozen=True, slots=True)
class ContextPiece:
    """One ranked, attributable piece of assembled context.

    `score` and `source` travel with the text because a caller assembling a
    prompt has to be able to answer why a piece is in it — a brief that cites
    the brain should be traceable to the file it came from without a join.
    """

    source: str
    text: str
    policy: str
    score: float


def _may_leave(document_policy: str, run_policy: str) -> bool:
    """Is this document eligible for a run executing under `run_policy`?

    A `local-only` run keeps everything on the machine, so every document is
    eligible. A `cloud-assisted` run may send what it assembles to a remote
    provider, so only `cloud-assisted` documents are eligible — this is the
    single place the airlock's assembly-side guarantee is enforced, and it is
    deliberately not configurable.
    """
    if run_policy == LOCAL_ONLY:
        return True
    return document_policy != LOCAL_ONLY


def collect_documents(
    repo: Repository, brain: BrainRepo, *, commit: str | None = None
) -> list[Document]:
    """Everything indexable, from the database and the brain.

    `commit` pins the brain to a run's `brain_sha`. Reading the working tree
    while a run claims a commit would make the pinning decorative — the same
    argument `BrainRepo.topic_files_at` was written for.
    """
    documents = [
        Document(
            source=f"entry:{row['id']}",
            text=row["raw_text"],
            policy=row["default_policy"],
        )
        for row in repo.entries_for_index()
    ]

    # What the person decided, and what became of what the night built. Both
    # belong to one entry, so both carry that entry's policy rather than the
    # brain's blanket one — the rubric scores using a prior decision above using
    # the profile, and neither was indexed at all.
    documents += [
        Document(
            source=f"decision:{row['id']}",
            text=f"You were asked: {row['question']}\nYou answered: {row['answer']}",
            policy=row["default_policy"],
        )
        for row in repo.answered_decisions_for_index()
    ]
    documents += [
        Document(
            source=f"outcome:{row['id']}",
            text=" ".join(
                part for part in (row["label"], row["signal"], row["note"]) if part
            ),
            policy=row["default_policy"],
        )
        for row in repo.outcomes_for_index()
    ]

    try:
        topics = brain.topic_files_at(commit) if commit else brain.topic_files()
    except BrainUnavailable:
        # A brain that is absent or not yet a git repository is a younger
        # system, not a broken one. Entries alone are still worth searching,
        # and a first run should not fail because memory is empty.
        return documents

    for source, text in (
        ("brain:profile", topics.profile),
        ("brain:style-guide", topics.style_guide),
    ):
        if text.strip():
            documents.append(Document(source=source, text=text, policy=BRAIN_POLICY))
    for name, text in sorted(topics.skills.items()):
        if text.strip():
            documents.append(
                Document(
                    source=f"brain:skill:{name}", text=text, policy=BRAIN_POLICY
                )
            )

    documents += _night_documents(repo, brain, commit)
    return documents


def _strictest(*policies: str) -> str:
    """The most restrictive of the policies given. `local-only` wins."""
    return BRAIN_POLICY if any(p == BRAIN_POLICY for p in policies) else CLOUD_ASSISTED


def _night_documents(
    repo: Repository, brain: BrainRepo, commit: str | None
) -> list[Document]:
    """What each night distilled, under the policy of the work behind it.

    A topic file is distilled across every entry, which is why ADR 0010 gives
    the brain a blanket `local-only`: there is no provenance to read. A night
    file has exactly one run behind it, and its name carries that run's id, so
    the policy here is read rather than assumed — the stricter of the run's own
    policy and its entry's, because a widened run still worked on private
    material.

    A file whose run cannot be resolved is `local-only`. An unreadable origin is
    not an open one.
    """
    try:
        files = brain.night_files_at(commit) if commit else brain.night_files()
    except BrainUnavailable:
        return []
    if not files:
        return []

    by_run = {
        row["id"]: _strictest(row["effective_policy"], row["default_policy"])
        for row in repo.run_provenance()
    }
    documents: list[Document] = []
    for name, text in sorted(files.items()):
        if not text.strip():
            continue
        run_id = name.removesuffix(".md").split("-")[-1]
        documents.append(
            Document(
                source=f"night:{run_id}",
                text=text,
                policy=by_run.get(run_id, BRAIN_POLICY),
            )
        )
    return documents


class RetrievalIndex:
    """Vectors over the corpus, rebuilt rather than stored."""

    def __init__(self, embedder: Embedder, *, dimensions: int = 2048) -> None:
        self._embedder = embedder
        self._dimensions = dimensions
        self._documents: list[Document] = []
        self._vectors = np.zeros((0, dimensions), dtype=np.float32)

    @property
    def documents(self) -> list[Document]:
        return list(self._documents)

    @property
    def vectors(self) -> np.ndarray:
        return self._vectors

    def __len__(self) -> int:
        return len(self._documents)

    def rebuild(
        self,
        repo: Repository,
        brain: BrainRepo,
        *,
        commit: str | None = None,
        policy: str = LOCAL_ONLY,
    ) -> None:
        """Re-read the corpus and re-embed it.

        `policy` is the policy the *embedding call itself* runs under, not the
        policy of what is being embedded. It is `local-only` by default because
        embedding is local on every profile, and passing anything else would ask
        the airlock to permit a call that should never be remote.
        """
        documents = collect_documents(repo, brain, commit=commit)
        self.load(documents, policy=policy)

    def load(self, documents: list[Document], *, policy: str = LOCAL_ONLY) -> None:
        """Embed and hold an explicit corpus. `rebuild` is this, plus the read."""
        if not documents:
            self._documents = []
            self._vectors = np.zeros((0, self._dimensions), dtype=np.float32)
            return

        raw = self._embedder.embed([d.text for d in documents], policy=policy)
        vectors = np.asarray(raw, dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[0] != len(documents):
            raise ValueError(
                f"embedder returned {vectors.shape} for {len(documents)} documents"
            )
        self._documents = list(documents)
        self._dimensions = int(vectors.shape[1])
        self._vectors = _normalize(vectors)

    def embed_query(self, query: str) -> list[float]:
        """One query vector, embedded by the same embedder as the corpus.

        Always under `local-only`: the query is assembled from the caller's own
        material, and the embedding call is local on every profile.
        """
        return self._embedder.embed([query], policy=LOCAL_ONLY)[0]

    def search(self, query_vector: list[float], k: int) -> list[ContextPiece]:
        """The `k` closest documents, by exact cosine, highest first.

        Ties break on source identifier rather than on array order, so a corpus
        read back in a different order ranks identically. `np.argsort` is stable
        but the order it is stabilizing is the corpus's, which is not a
        guarantee anything else makes.
        """
        if k <= 0 or not self._documents:
            return []
        query = _normalize(np.asarray([query_vector], dtype=np.float32))[0]
        if query.shape[0] != self._vectors.shape[1]:
            raise ValueError(
                f"query is {query.shape[0]}-dim against a "
                f"{self._vectors.shape[1]}-dim index"
            )
        # Both sides are unit vectors, so the dot product is the cosine.
        scores = self._vectors @ query
        ranked = sorted(
            zip(scores.tolist(), self._documents),
            key=lambda pair: (-pair[0], pair[1].source),
        )
        return [
            ContextPiece(
                source=document.source,
                text=document.text,
                policy=document.policy,
                score=float(score),
            )
            for score, document in ranked[:k]
        ]


def assemble_context(
    index: RetrievalIndex,
    query: str,
    *,
    policy: str,
    max_pieces: int = 5,
    exclude: frozenset[str] = frozenset(),
) -> list[ContextPiece]:
    """Bounded, ordered, policy-filtered context for one query.

    The filter runs before this returns. A caller never receives a structure
    holding `local-only` text under a `cloud-assisted` run, so there is no
    window in which the wrong thing could be serialized — which is what
    principle 2 asks for, and why the filter is not a flag.

    Searches wider than `max_pieces` because filtering happens after ranking:
    taking the top five and then dropping the local-only ones would silently
    return fewer pieces than asked for whenever the best matches were the
    private ones.

    `exclude` names sources that must not come back — the entry being worked,
    above all, which is otherwise its own closest match and is handed to the
    brief as memory of earlier work. Applied before the bound, for the same
    reason as the policy filter.
    """
    if max_pieces <= 0 or not len(index):
        return []
    query_vector = index.embed_query(query)
    ranked = index.search(query_vector, len(index))
    eligible = [
        p for p in ranked if _may_leave(p.policy, policy) and p.source not in exclude
    ]
    return eligible[:max_pieces]


def _normalize(vectors: np.ndarray) -> np.ndarray:
    """Unit-length rows, so a dot product is a cosine.

    A zero vector normalizes to itself rather than to NaN: an embedder that
    returns zeros is a problem to see in the scores, not a crash halfway
    through assembly.
    """
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1.0, norms)
