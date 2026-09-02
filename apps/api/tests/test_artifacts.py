"""The writer, the variant fields, and the outcomes that make the cost view work.

`test_rank_is_never_the_generation_order` is the load-bearing one. The prompt
that specified this capability names "a ranking that is really the generation
order" on the never-ship list, and the synthetic night generates shuffled ranks
precisely so a renderer that assumes rank equals index is wrong on that data.

Its mutation was run: making `rank_group` write `variant_index` instead of the
critic's position turns it red. So did making `write_variants` pass
`variant_rank=index` at insert time — which it structurally cannot do, because
`write_artifact` takes no rank parameter at all.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from secondshift.artifacts.store import (
    ArtifactWriteFailed,
    artifact_root,
    default_root,
    relative_path,
    verify,
    write_artifact,
)
from secondshift.artifacts.variants import (
    RankingRefused,
    parse_ordering,
    rank_group,
    write_variants,
)
from secondshift.db.connection import now_ms


@pytest.fixture
def run(repo):
    entry = repo.insert_entry(
        created_at_ms=now_ms(),
        captured_tz="UTC",
        tz_offset_min=0,
        modality="text",
        default_policy="cloud-assisted",
        status="queued",
        capture_profile="spark",
        raw_text="an idea",
    )
    run_id = repo.insert_run(
        entry_id=entry,
        night_of="2026-09-02",
        effective_policy="cloud-assisted",
        policy_source="entry-default",
        compute_profile="spark",
    )
    return entry, run_id


@pytest.fixture
def write(repo, run, tmp_path):
    entry, run_id = run

    def _write(kind: str = "brief", content: str = "# A brief\n\nBody.\n", **kw):
        return write_artifact(
            repo,
            run_id=run_id,
            entry_id=entry,
            night_of="2026-09-02",
            stage=kw.pop("stage", "brief"),
            kind=kind,
            content=content,
            root=tmp_path,
            **kw,
        )

    return _write


class TestTheRecordDescribesWhatLanded:
    def test_the_hash_is_of_the_file_not_of_the_intent(self, repo, write, tmp_path):
        """A hash computed from the string proves what was meant, not what
        landed — and the column exists to detect the difference."""
        content = "# A brief\n\nBody.\n"
        written = write(content=content)

        on_disk = (tmp_path / written.path).read_bytes()
        assert written.content_sha == hashlib.sha256(on_disk).hexdigest()
        assert written.bytes == len(on_disk)

    def test_a_short_write_is_recorded_as_what_landed(
        self, repo, run, tmp_path, monkeypatch
    ):
        """The case the read-back exists for, and the one a normal write cannot
        show: when the bytes on disk differ from the string that was passed in.

        Found by mutation. Replacing the read-back with `content.encode()` left
        every other test in this class green, because for a successful write the
        two are identical — which means the design decision this module argues
        for had no test behind it at all.
        """
        entry, run_id = run
        real_write = Path.write_text

        def short_write(self, data, *args, **kwargs):
            return real_write(self, data[: len(data) // 2], *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", short_write)

        intended = "# A brief\n\nThe second half of this is lost.\n"
        written = write_artifact(
            repo,
            run_id=run_id,
            entry_id=entry,
            night_of="2026-09-02",
            stage="brief",
            kind="brief",
            content=intended,
            root=tmp_path,
        )
        monkeypatch.undo()

        on_disk = (tmp_path / written.path).read_bytes()
        assert len(on_disk) < len(intended.encode())
        assert written.bytes == len(on_disk)
        assert written.content_sha == hashlib.sha256(on_disk).hexdigest()
        assert written.content_sha != hashlib.sha256(intended.encode()).hexdigest()

    def test_the_row_carries_the_same_hash(self, repo, write):
        written = write()

        row = repo.connection.execute(
            "SELECT * FROM artifacts WHERE id = ?", (written.artifact_id,)
        ).fetchone()
        assert row["content_sha"] == written.content_sha
        assert row["bytes"] == written.bytes

    def test_a_corrupted_file_no_longer_verifies(self, repo, write, tmp_path):
        written = write()
        row = repo.connection.execute(
            "SELECT * FROM artifacts WHERE id = ?", (written.artifact_id,)
        ).fetchone()
        assert verify(row, root=tmp_path)

        (tmp_path / written.path).write_text("something else entirely")

        assert not verify(row, root=tmp_path)

    def test_a_truncated_file_no_longer_verifies(self, repo, write, tmp_path):
        """The case the byte count is for, separately from the hash."""
        written = write()
        row = repo.connection.execute(
            "SELECT * FROM artifacts WHERE id = ?", (written.artifact_id,)
        ).fetchone()

        (tmp_path / written.path).write_text("")

        assert not verify(row, root=tmp_path)

    def test_a_missing_file_no_longer_verifies(self, repo, write, tmp_path):
        written = write()
        row = repo.connection.execute(
            "SELECT * FROM artifacts WHERE id = ?", (written.artifact_id,)
        ).fetchone()

        (tmp_path / written.path).unlink()

        assert not verify(row, root=tmp_path)

    def test_a_failed_write_records_no_row(self, repo, run, tmp_path):
        """A row pointing at a file that is not there records a provenance
        nobody can check — the same defect as recording none."""
        entry, run_id = run
        blocked = tmp_path / "blocked"
        blocked.write_text("this is a file, not a directory")

        with pytest.raises(ArtifactWriteFailed):
            write_artifact(
                repo,
                run_id=run_id,
                entry_id=entry,
                night_of="2026-09-02",
                stage="brief",
                kind="brief",
                content="x",
                root=blocked,
            )

        assert list(repo.connection.execute("SELECT * FROM artifacts")) == []

    def test_an_artifact_resolves_to_its_invocation(self, repo, write, agent_id, run):
        entry, run_id = run
        invocation = repo.insert_agent_invocation(
            agent_id=agent_id, run_id=run_id, depth=0, stage="brief"
        )

        written = write(produced_by_invocation_id=invocation)

        row = repo.connection.execute(
            "SELECT * FROM artifacts WHERE id = ?", (written.artifact_id,)
        ).fetchone()
        assert row["produced_by_invocation_id"] == invocation


class TestTheLayout:
    def test_two_runs_on_one_night_do_not_collide(self, repo, run, tmp_path):
        """The defect in the convention the seed established: keyed on the
        night alone, two entries worked the same night overwrite each other."""
        first = relative_path(night_of="2026-09-02", run_id="RUN_A", kind="brief")
        second = relative_path(night_of="2026-09-02", run_id="RUN_B", kind="brief")

        assert first != second

    def test_a_stored_path_is_relative_and_carries_no_location(self, write):
        """An absolute path pins a home directory into rows a judge reads."""
        written = write()

        assert not written.path.startswith("/")
        assert "home" not in written.path
        assert ".." not in written.path

    def test_variants_of_one_kind_are_separated_by_index(self):
        a = relative_path(night_of="2026-09-02", run_id="R", kind="build", variant_index=0)
        b = relative_path(night_of="2026-09-02", run_id="R", kind="build", variant_index=1)

        assert a != b

    def test_a_variant_kind_without_an_index_is_refused(self):
        with pytest.raises(ValueError, match="needs a variant_index"):
            relative_path(night_of="2026-09-02", run_id="R", kind="build")

    def test_a_single_kind_with_an_index_is_refused(self):
        with pytest.raises(ValueError, match="not a variant kind"):
            relative_path(
                night_of="2026-09-02", run_id="R", kind="brief", variant_index=0
            )

    def test_an_unknown_kind_is_refused_rather_than_guessed(self):
        with pytest.raises(ValueError, match="no filename is defined"):
            relative_path(night_of="2026-09-02", run_id="R", kind="nonsense")

    def test_the_root_is_configuration(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SECOND_SHIFT_ARTIFACTS", str(tmp_path / "elsewhere"))

        assert artifact_root() == tmp_path / "elsewhere"

    def test_the_default_root_sits_beside_the_database(self, monkeypatch):
        monkeypatch.delenv("SECOND_SHIFT_ARTIFACTS", raising=False)

        assert default_root().name == "artifacts"


class TestGroupIndexAndRankAreThreeThings:
    @pytest.fixture
    def group(self, repo, run, tmp_path):
        entry, run_id = run
        return write_variants(
            repo,
            run_id=run_id,
            entry_id=entry,
            night_of="2026-09-02",
            stage="build",
            kind="build",
            contents=[f"variant {i} body" for i in range(5)],
            root=tmp_path,
        )

    def test_variants_share_a_group_and_have_distinct_indices(self, repo, group):
        rows = repo.connection.execute(
            "SELECT * FROM artifacts WHERE variant_group = ?", (group.group,)
        ).fetchall()

        assert len(rows) == 5
        assert {r["variant_index"] for r in rows} == set(range(5))

    def test_nothing_is_ranked_before_a_critic_speaks(self, repo, group):
        """The failure this capability is written against. A rank that is really
        the generation order looks like evidence and is not."""
        rows = repo.connection.execute(
            "SELECT variant_rank FROM artifacts WHERE variant_group = ?", (group.group,)
        ).fetchall()

        assert all(r["variant_rank"] is None for r in rows)

    def test_rank_is_never_the_generation_order(self, repo, group):
        """Ranked worst-to-best relative to index, so a ranker that copied the
        index would produce the opposite of what this asserts."""
        rank_group(repo, group.group, [4, 3, 2, 1, 0])

        by_index = {
            r["variant_index"]: r["variant_rank"]
            for r in repo.connection.execute(
                "SELECT variant_index, variant_rank FROM artifacts "
                "WHERE variant_group = ?",
                (group.group,),
            )
        }
        assert by_index == {4: 1, 3: 2, 2: 3, 1: 4, 0: 5}
        assert all(index != rank for index, rank in by_index.items())

    def test_the_synthetic_night_s_ranks_are_not_its_indices(self, repo):
        """Asserted against the seed, whose ranks are a shuffled permutation on
        purpose — anything reading these fields has to survive that."""
        from secondshift_seed.night import generate_night

        generate_night(repo, seed=42)

        rows = repo.connection.execute(
            "SELECT variant_index, variant_rank FROM artifacts "
            "WHERE variant_group IS NOT NULL AND variant_rank IS NOT NULL"
        ).fetchall()
        assert rows, "the seed wrote no ranked variants"
        assert any(r["variant_index"] != r["variant_rank"] - 1 for r in rows)


class TestAPartialRankingIsRefused:
    @pytest.fixture
    def group(self, repo, run, tmp_path):
        entry, run_id = run
        return write_variants(
            repo,
            run_id=run_id,
            entry_id=entry,
            night_of="2026-09-02",
            stage="build",
            kind="build",
            contents=["a", "b", "c"],
            root=tmp_path,
        )

    def _ranks(self, repo, group):
        return [
            r["variant_rank"]
            for r in repo.connection.execute(
                "SELECT variant_rank FROM artifacts WHERE variant_group = ?",
                (group.group,),
            )
        ]

    def test_an_ordering_that_omits_a_variant_writes_nothing(self, repo, group):
        with pytest.raises(RankingRefused, match="does not cover exactly"):
            rank_group(repo, group.group, [0, 1])

        assert self._ranks(repo, group) == [None, None, None]

    def test_an_ordering_that_repeats_a_variant_writes_nothing(self, repo, group):
        with pytest.raises(RankingRefused):
            rank_group(repo, group.group, [0, 1, 1])

        assert self._ranks(repo, group) == [None, None, None]

    def test_an_ordering_naming_an_unknown_variant_writes_nothing(self, repo, group):
        with pytest.raises(RankingRefused):
            rank_group(repo, group.group, [0, 1, 9])

        assert self._ranks(repo, group) == [None, None, None]

    def test_ranking_an_empty_group_is_refused(self, repo):
        with pytest.raises(RankingRefused, match="no variants exist"):
            rank_group(repo, "no-such-group", [0])


class TestParsingTheCriticsOrdering:
    def test_it_reads_variant_numbers_in_order(self):
        assert parse_ordering(
            "Variant 3 is strongest. Then variant 0, and finally Variant 1."
        ) == [3, 0, 1]

    def test_a_bare_number_is_not_an_index(self):
        """Token counts and years appear in critic prose. A pattern that matched
        bare integers would rank a group by its own word count."""
        assert parse_ordering("Took 2048 tokens in 2026. Variant 1 wins.") == [1]

    def test_a_repeat_is_preserved_rather_than_collapsed(self):
        """Silently deduplicating would hide an ordering nobody should apply."""
        assert parse_ordering("Variant 1, then variant 1 again.") == [1, 1]


class TestAPartialFanOutKeepsWhatLanded:
    def test_a_failed_variant_does_not_remove_its_siblings(self, repo, run, tmp_path):
        """Principle 3: a fan-out where one variant's failure loses the other
        four is the violation, named in the prompt."""
        entry, run_id = run

        produced = write_variants(
            repo,
            run_id=run_id,
            entry_id=entry,
            night_of="2026-09-02",
            stage="build",
            kind="build",
            contents=["a", None, "c", None, "e"],
            root=tmp_path,
        )

        assert len(produced.written) == 3
        assert produced.failed == [1, 3]
        for w in produced.written:
            assert (tmp_path / w.path).exists()

    def test_a_partly_produced_group_cannot_be_ranked_by_the_full_ordering(
        self, repo, run, tmp_path
    ):
        """The refusal composes with the partial fan-out: an ordering naming
        five variants against a group holding three is not applied."""
        entry, run_id = run
        produced = write_variants(
            repo,
            run_id=run_id,
            entry_id=entry,
            night_of="2026-09-02",
            stage="build",
            kind="build",
            contents=["a", None, "c", None, "e"],
            root=tmp_path,
        )

        with pytest.raises(RankingRefused):
            rank_group(repo, produced.group, [0, 1, 2, 3, 4])


class TestOutcomes:
    def test_an_outcome_needs_a_label_or_a_signal(self, repo, run):
        entry, _ = run

        with pytest.raises(ValueError, match="needs a label"):
            repo.insert_outcome(entry_id=entry)

    def test_recording_a_keep_makes_the_cost_view_return_a_number(
        self, repo, run, write, agent_id
    ):
        entry, run_id = run
        written = write()
        repo.insert_model_call(
            run_id=run_id,
            provider="token-factory",
            compute_profile="spark",
            model="nemotron-3-super",
            policy="cloud-assisted",
            prompt_tokens=1000,
            completion_tokens=1000,
            estimated_cost_usd=0.004,
        )

        repo.insert_outcome(entry_id=entry, artifact_id=written.artifact_id, label="keep")

        row = repo.connection.execute(
            "SELECT * FROM cost_per_accepted_artifact WHERE night_of = '2026-09-02'"
        ).fetchone()
        assert row["accepted"] == 1
        assert row["usd_per_accepted"] is not None

    def test_without_an_outcome_the_view_reports_nothing_accepted(
        self, repo, run, write
    ):
        """What is true today across the whole system: `outcomes` has never had
        a writer, so this chart has never returned a number."""
        entry, run_id = run
        write()
        repo.insert_model_call(
            run_id=run_id,
            provider="token-factory",
            compute_profile="spark",
            model="nemotron-3-super",
            policy="cloud-assisted",
            prompt_tokens=10,
            completion_tokens=10,
            estimated_cost_usd=0.001,
        )

        row = repo.connection.execute(
            "SELECT * FROM cost_per_accepted_artifact WHERE night_of = '2026-09-02'"
        ).fetchone()
        assert row["accepted"] == 0
        assert row["usd_per_accepted"] is None

    def test_ranking_a_group_accepts_nothing(self, repo, run, tmp_path):
        """If a rank implied a keep, the submission's headline chart would be
        measuring the critic agreeing with itself."""
        entry, run_id = run
        produced = write_variants(
            repo,
            run_id=run_id,
            entry_id=entry,
            night_of="2026-09-02",
            stage="build",
            kind="build",
            contents=["a", "b"],
            root=tmp_path,
        )

        rank_group(repo, produced.group, [1, 0])

        assert list(repo.connection.execute("SELECT * FROM outcomes")) == []
