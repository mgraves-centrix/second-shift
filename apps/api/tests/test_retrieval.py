"""Retrieval: the embedder client, the index, and the airlock at assembly.

The airlock test in `TestTheAirlockAtAssembly` is the one this capability rests
on. It is written so that removing the policy filter turns it red — a test that
cannot fail is decoration, and this is the one place where decoration would be
indistinguishable from a privacy guarantee.
"""

from __future__ import annotations

import subprocess

import pytest

from secondshift import config
from secondshift.brain.repo import BrainRepo
from secondshift.db.connection import now_ms
from secondshift.providers.base import Embedder
from secondshift.providers.registry import LocalEmbedderNotConfigured, Registry
from secondshift.providers.vllm_embed import (
    EmbedderTimeout,
    EmbedderUnavailable,
    VllmEmbedder,
)
from secondshift.retrieval import ContextPiece, Document, RetrievalIndex, assemble_context
from secondshift.retrieval.index import collect_documents
from secondshift.telemetry.failures import BadOutput

TZ = dict(captured_tz="America/Los_Angeles", tz_offset_min=-420)

#: A tiny vocabulary. Each document becomes a bag-of-words vector over it, so
#: "obviously matching" genuinely matches by cosine rather than by a stub that
#: was told which answer to give.
VOCAB = ["sourdough", "starter", "rye", "kubernetes", "cluster", "yaml", "tax", "invoice"]


class WordEmbedder(Embedder):
    """Deterministic bag-of-words vectors over a fixed vocabulary.

    Not a mock of the thing under test: what is under test is the index, the
    ranking and the policy filter. This supplies the vectors those operate on,
    the way a real embedder would, and it is deterministic across processes —
    which `HashEmbedder` is not, because `hash()` is salted per interpreter.
    """

    provider_kind = "local-vllm"

    def _do_embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            lowered = text.lower()
            vectors.append([float(lowered.count(word)) for word in VOCAB])
        return vectors


@pytest.fixture
def embedder(recorder) -> WordEmbedder:
    return WordEmbedder(recorder, model="word-test")


@pytest.fixture
def index(embedder) -> RetrievalIndex:
    return RetrievalIndex(embedder, dimensions=len(VOCAB))


@pytest.fixture
def brain(tmp_path) -> BrainRepo:
    """A real git repository, because the code shells out to a real git."""
    path = tmp_path / "brain"
    (path / "skills").mkdir(parents=True)
    (path / "profile.md").write_text("I bake sourdough with a rye starter.\n")
    (path / "style-guide.md").write_text("Direct sentences.\n")
    (path / "skills" / "README.md").write_text("# Skills\n")
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "test@example.invalid"],
        ["config", "user.name", "Test"],
        ["add", "-A"],
        ["commit", "-q", "-m", "seed"],
    ):
        subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)
    return BrainRepo(path)


def _capture(repo, text, *, policy="cloud-assisted"):
    return repo.insert_entry(
        created_at_ms=now_ms(),
        modality="text",
        default_policy=policy,
        status="queued",
        capture_profile="spark",
        raw_text=text,
        **TZ,
    )


# -- the embedder client ---------------------------------------------------


def _embeddings(vectors: list[list[float]], *, indices: list[int] | None = None) -> dict:
    order = indices if indices is not None else list(range(len(vectors)))
    return {
        "object": "list",
        "data": [
            {"object": "embedding", "index": i, "embedding": v}
            for i, v in zip(order, vectors)
        ],
    }


@pytest.fixture
def embedder_settings(vllm_stub):
    return config.LocalEmbedderSettings(
        host=vllm_stub.host,
        port=vllm_stub.port,
        model="stub-embed-model",
        dimensions=3,
        timeout_s=5,
    )


class TestTheEmbedderClient:
    def test_vectors_come_back_in_request_order_not_arrival_order(
        self, recorder, vllm_stub, embedder_settings
    ):
        """The response's own `index` orders the result, not the array position.

        The OpenAI embeddings schema carries an index precisely because the
        array is not promised to be in request order. A caller zipping vectors
        onto its documents positionally would attach the wrong vector to the
        wrong document, and every shape check would still pass.
        """
        vllm_stub.body = _embeddings(
            [[9.0, 9.0, 9.0], [1.0, 0.0, 0.0]], indices=[1, 0]
        )
        vllm_stub.raw = None
        client = VllmEmbedder(recorder, settings=embedder_settings)

        assert client.embed(["first", "second"], policy="local-only") == [
            [1.0, 0.0, 0.0],
            [9.0, 9.0, 9.0],
        ]

    def test_a_width_that_disagrees_with_configuration_is_refused(
        self, recorder, vllm_stub, embedder_settings
    ):
        """A server swapped for a different model is a loud failure.

        Silently accepting a 4-dim vector where 3 was configured would build an
        index nothing can search against, and the first symptom would be a
        ranking that looks merely bad.
        """
        vllm_stub.body = _embeddings([[1.0, 0.0, 0.0, 0.0]])
        vllm_stub.raw = None
        client = VllmEmbedder(recorder, settings=embedder_settings)

        with pytest.raises(BadOutput, match="4-dim vector where 3 was configured"):
            client.embed(["one"], policy="local-only")

    def test_fewer_vectors_than_inputs_is_refused(
        self, recorder, vllm_stub, embedder_settings
    ):
        vllm_stub.body = _embeddings([[1.0, 0.0, 0.0]])
        vllm_stub.raw = None
        client = VllmEmbedder(recorder, settings=embedder_settings)

        with pytest.raises(BadOutput, match="1 vectors for 2 inputs"):
            client.embed(["one", "two"], policy="local-only")

    def test_an_unreachable_server_raises_and_is_recorded(
        self, recorder, repo, run_id, agent_id
    ):
        """A closed port is a network failure, and the ledger gets a row.

        The base class records it; nothing in `vllm_embed.py` writes telemetry.
        """
        settings = config.LocalEmbedderSettings(
            host="127.0.0.1", port=1, model="m", dimensions=3, timeout_s=1
        )
        client = VllmEmbedder(recorder, settings=settings)

        with recorder.invocation(agent_id, run_id=run_id):
            with pytest.raises(EmbedderUnavailable):
                client.embed(["one"], policy="local-only")

        rows = list(repo.connection.execute("SELECT * FROM failures"))
        assert [r["type"] for r in rows] == ["network"]

    def test_a_slow_server_is_a_timeout_not_a_network_fault(
        self, recorder, vllm_stub, embedder_settings
    ):
        """The taxonomy separates absent from too-slow, so the types must too."""
        vllm_stub.body = _embeddings([[1.0, 0.0, 0.0]])
        vllm_stub.raw = None
        vllm_stub.delay_s = 0.5
        settings = config.LocalEmbedderSettings(
            host=embedder_settings.host,
            port=embedder_settings.port,
            model="m",
            dimensions=3,
            timeout_s=0.05,
        )
        client = VllmEmbedder(recorder, settings=settings)

        with pytest.raises(EmbedderTimeout):
            client.embed(["one"], policy="local-only")

    def test_embedding_no_texts_calls_nothing(self, recorder, embedder_settings):
        client = VllmEmbedder(recorder, settings=embedder_settings)
        assert client.embed([], policy="local-only") == []


# -- the index -------------------------------------------------------------


class TestTheIndex:
    def test_it_holds_float32_of_the_embedder_s_width(self, index):
        index.load([Document("a", "sourdough", "cloud-assisted")])

        assert index.vectors.dtype.name == "float32"
        assert index.vectors.shape == (1, len(VOCAB))

    def test_sources_name_where_each_document_came_from(self, repo, brain, index):
        _capture(repo, "sourdough notes")
        documents = collect_documents(repo, brain)

        sources = {d.source for d in documents}
        assert any(s.startswith("entry:") for s in sources)
        assert "brain:profile" in sources
        assert "brain:style-guide" in sources

    def test_an_obvious_match_outranks_an_obvious_non_match(self, index):
        index.load(
            [
                Document("doc:bread", "sourdough starter rye", "cloud-assisted"),
                Document("doc:ops", "kubernetes cluster yaml", "cloud-assisted"),
            ]
        )

        ranked = index.search(index.embed_query("sourdough starter"), 2)

        assert ranked[0].source == "doc:bread"
        assert ranked[0].score > ranked[1].score

    def test_ties_break_the_same_way_whatever_order_the_corpus_arrived_in(self, index):
        """Two identical documents must rank identically on a reread.

        Corpus order is an accident of `ORDER BY created_at_ms, id` and a
        directory listing. Ranking that inherits it is ranking that changes when
        nothing changed.
        """
        first = Document("doc:b", "rye", "cloud-assisted")
        second = Document("doc:a", "rye", "cloud-assisted")

        index.load([first, second])
        forward = [p.source for p in index.search(index.embed_query("rye"), 2)]
        index.load([second, first])
        backward = [p.source for p in index.search(index.embed_query("rye"), 2)]

        assert forward == backward == ["doc:a", "doc:b"]

    def test_rebuilding_after_discarding_returns_identical_results(
        self, repo, brain, index, embedder
    ):
        """The index is derived. Deleting it must lose nothing."""
        _capture(repo, "sourdough starter notes")
        _capture(repo, "kubernetes cluster notes")
        index.rebuild(repo, brain)
        before = index.search(index.embed_query("sourdough"), 5)

        fresh = RetrievalIndex(embedder, dimensions=len(VOCAB))
        fresh.rebuild(repo, brain)
        after = fresh.search(fresh.embed_query("sourdough"), 5)

        assert [(p.source, p.score) for p in before] == [
            (p.source, p.score) for p in after
        ]

    def test_a_query_of_the_wrong_width_is_refused(self, index):
        index.load([Document("a", "rye", "cloud-assisted")])

        with pytest.raises(ValueError, match="against a"):
            index.search([1.0, 2.0], 1)

    def test_an_empty_corpus_searches_to_nothing(self, index):
        index.load([])
        assert index.search([0.0] * len(VOCAB), 3) == []


class TestReadingTheBrainAtAPinnedCommit:
    def test_two_commits_return_what_each_actually_held(self, repo, brain, index):
        """Pinning must read history, not the working tree.

        A run records `brain_sha` so its output can be attributed to the memory
        that produced it. Reading HEAD instead would make that attribution a
        label rather than a fact.
        """
        first = brain.head()
        (brain.path / "profile.md").write_text("I bake with kubernetes now.\n")
        subprocess.run(
            ["git", "-C", str(brain.path), "commit", "-qam", "changed"],
            check=True,
            capture_output=True,
        )
        second = brain.head()

        old = {d.source: d.text for d in collect_documents(repo, brain, commit=first)}
        new = {d.source: d.text for d in collect_documents(repo, brain, commit=second)}

        assert "sourdough" in old["brain:profile"]
        assert "kubernetes" in new["brain:profile"]

    def test_a_missing_brain_leaves_entries_searchable(self, repo, tmp_path):
        """A younger system has no brain yet. That is not a failure."""
        _capture(repo, "sourdough notes")

        documents = collect_documents(repo, BrainRepo(tmp_path / "absent"))

        assert [d.source.split(":")[0] for d in documents] == ["entry"]


# -- the airlock, at assembly ----------------------------------------------


class TestTheAirlockAtAssembly:
    """Principle 2, enforced where context is built rather than where it is sent.

    Every test here is written to go red if the policy filter in
    `assemble_context` is removed. That is the point: this is the only guarantee
    standing between a private idea and a remote provider, and a green suite
    that would stay green without the guard would be worse than no suite.
    """

    def test_a_local_only_entry_never_reaches_cloud_assisted_context(self, index, repo):
        """The best match is private. It must not be in what a cloud run sends.

        Delete the `_may_leave` filter from `assemble_context` and this fails —
        the local-only document is the strongest cosine match by construction,
        so it would rank first and be returned.
        """
        private = "sourdough starter rye sourdough"
        index.load(
            [
                Document("entry:private", private, "local-only"),
                Document("entry:public", "sourdough", "cloud-assisted"),
            ]
        )

        pieces = assemble_context(index, "sourdough starter", policy="cloud-assisted")

        assert [p.source for p in pieces] == ["entry:public"]
        for piece in pieces:
            assert private not in piece.text
            assert "starter rye" not in piece.text

    def test_the_same_entry_is_available_to_a_local_only_run(self, index):
        """Filtering is about egress, not about hiding memory from its owner."""
        index.load(
            [
                Document("entry:private", "sourdough starter rye", "local-only"),
                Document("entry:public", "sourdough", "cloud-assisted"),
            ]
        )

        pieces = assemble_context(index, "sourdough starter", policy="local-only")

        assert [p.source for p in pieces] == ["entry:private", "entry:public"]

    def test_brain_content_does_not_leave_under_cloud_assisted(self, repo, brain, index):
        """The brain is local-only until somebody decides otherwise on the record.

        `openspec/constitution.md` says the brain itself never leaves; a topic
        file distilled from local-only material inherits that until a change
        argues otherwise. This test is what makes that decision visible if it is
        ever reversed by accident.
        """
        index.rebuild(repo, brain)

        pieces = assemble_context(index, "sourdough rye", policy="cloud-assisted")

        assert not any(p.source.startswith("brain:") for p in pieces)

    def test_filtering_happens_before_the_bound_is_applied(self, index):
        """Otherwise a private top match silently costs the caller a slot.

        Ranking, then truncating to `max_pieces`, then filtering would return
        one piece here instead of two — and the caller would have no way to tell
        a short result from a small corpus.
        """
        index.load(
            [
                Document("entry:private", "sourdough starter rye", "local-only"),
                Document("entry:a", "sourdough starter", "cloud-assisted"),
                Document("entry:b", "sourdough", "cloud-assisted"),
            ]
        )

        pieces = assemble_context(
            index, "sourdough starter", policy="cloud-assisted", max_pieces=2
        )

        assert [p.source for p in pieces] == ["entry:a", "entry:b"]


class TestWhatAssemblyReturns:
    def test_every_piece_carries_score_source_and_policy(self, index):
        index.load([Document("entry:a", "sourdough", "cloud-assisted")])

        [piece] = assemble_context(index, "sourdough", policy="cloud-assisted")

        assert isinstance(piece, ContextPiece)
        assert piece.source == "entry:a"
        assert piece.policy == "cloud-assisted"
        assert piece.score > 0

    def test_the_bound_is_respected(self, index):
        index.load(
            [
                Document(f"entry:{n}", "sourdough rye", "cloud-assisted")
                for n in range(10)
            ]
        )

        assert len(assemble_context(index, "sourdough", policy="cloud-assisted", max_pieces=3)) == 3

    def test_asking_for_nothing_returns_nothing_without_embedding(self, index):
        index.load([Document("entry:a", "sourdough", "cloud-assisted")])
        assert assemble_context(index, "sourdough", policy="cloud-assisted", max_pieces=0) == []

    def test_an_embedder_failure_reaches_the_caller(self, recorder):
        """Retrieval does not swallow a failure into an empty result.

        A caller that degrades to no context must be able to tell "nothing
        matched" from "embedding is down", because the second is a broken night
        and the first is an ordinary one.
        """

        class Broken(Embedder):
            provider_kind = "local-vllm"

            def _do_embed(self, texts: list[str]) -> list[list[float]]:
                raise EmbedderUnavailable("the server is down")

        index = RetrievalIndex(Broken(recorder, model="broken"), dimensions=len(VOCAB))

        with pytest.raises(EmbedderUnavailable, match="the server is down"):
            index.load([Document("entry:a", "sourdough", "cloud-assisted")])


# -- binding ---------------------------------------------------------------


class TestTheEmbedderIsLocalOnEveryProfile:
    def test_cloud_constructs_a_local_embedder_not_a_remote_one(self, recorder):
        """Principle 2 names a hosted embedding endpoint as a violation.

        Asserted at construction rather than at call time: "no remote call was
        made" is a statement about one test run, and "no remote provider was
        built" is a statement about the registry.
        """
        embedder = Registry(recorder).bind("cloud").embedder

        assert isinstance(embedder, VllmEmbedder)
        assert embedder.provider_kind == "local-vllm"

    def test_every_profile_binds_the_same_embedder_kind(self, recorder):
        kinds = {
            profile: Registry(recorder).bind(profile).embedder.provider_kind
            for profile in ("spark", "workstation", "cloud")
        }

        assert set(kinds.values()) == {"local-vllm"}

    def test_an_unconfigured_embedder_is_refused_rather_than_faked(
        self, recorder, monkeypatch
    ):
        """The hash placeholder returns the right shape and ranks by nothing.

        A refusal is the only way that failure becomes visible, because
        retrieval built on hashed vectors looks exactly like working retrieval
        from every direction except the results.
        """
        monkeypatch.setattr(config, "_embedder_config", dict)
        monkeypatch.delenv(config.ENV_EMBEDDER_MODEL, raising=False)

        with pytest.raises(LocalEmbedderNotConfigured, match="rank documents by nothing"):
            Registry(recorder).bind("cloud")


class TestConfiguration:
    def test_an_absent_embedder_block_yields_an_empty_model_not_a_crash(
        self, monkeypatch
    ):
        """Reading configuration and deciding what a gap means are separate jobs."""
        monkeypatch.setattr(config, "_embedder_config", dict)
        monkeypatch.delenv(config.ENV_EMBEDDER_MODEL, raising=False)

        settings = config.local_embedder_settings()

        assert settings.model == ""
        assert settings.port == 8201

    def test_the_environment_overrides_the_file(self, monkeypatch):
        monkeypatch.setenv(config.ENV_EMBEDDER_MODEL, "override-model")
        monkeypatch.setenv(config.ENV_EMBEDDER_PORT, "9999")

        settings = config.local_embedder_settings()

        assert settings.model == "override-model"
        assert settings.port == 9999

    def test_the_configured_model_is_the_one_the_deploy_unit_serves(self):
        """Configuration and the unit that serves it must not drift apart.

        They did once already, for the reasoner: the spike served on 8000 while
        the config allocated 8200, and the probe reported the reasoner missing.
        """
        unit = (
            config.Path(__file__).resolve().parents[3]
            / "deploy"
            / "spark"
            / "second-shift-embedder.service"
        ).read_text()
        settings = config.local_embedder_settings()

        assert f"--served-model-name {settings.model}" in unit
        assert f":{settings.port}:8000" in unit
