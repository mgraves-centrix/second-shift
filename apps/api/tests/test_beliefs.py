"""What the distiller is allowed to change about the brain, and how.

The brain is the claim: a `git diff` from week one to week eight is what makes
"it learned" visible. That diff is only worth reading if each change is a
belief somebody could argue with, and if nothing is ever lost to a parse.
"""

from __future__ import annotations

import subprocess

import pytest

from secondshift.brain.beliefs import (
    MAX_BELIEFS,
    Belief,
    apply_beliefs,
    parse_beliefs,
)
from secondshift.brain.repo import BrainRepo

WELL_FORMED = """
Here is what tonight suggests.

BELIEF: Prefers a brief short enough to read standing up.
REPLACES: Prefers short briefs.

BELIEF: Reads on a phone first.
REPLACES: none
"""


@pytest.fixture
def brain(tmp_path) -> BrainRepo:
    path = tmp_path / "brain"
    path.mkdir()
    (path / "profile.md").write_text("# Profile\n\nPrefers short briefs.\n")
    (path / "style-guide.md").write_text("# Style\n\nDirect sentences.\n")
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "test@example.invalid"],
        ["config", "user.name", "Test"],
        ["add", "-A"],
        ["commit", "-q", "-m", "seed"],
    ):
        subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)
    return BrainRepo(path)


class TestReadingWhatTheDistillerProposed:
    def test_a_belief_and_what_it_replaces_are_read_together(self):
        beliefs = parse_beliefs(WELL_FORMED)

        assert beliefs == [
            Belief("Prefers a brief short enough to read standing up.", "Prefers short briefs."),
            Belief("Reads on a phone first.", None),
        ]

    def test_prose_around_the_blocks_is_ignored(self):
        assert parse_beliefs("A paragraph.\n\nBELIEF: One thing.\nREPLACES: none\n") == [
            Belief("One thing.", None)
        ]

    def test_a_belief_without_its_replaces_line_is_discarded(self):
        """Half a block is a parse nobody should act on: the difference between
        revising a belief and adding one is the whole point of the format."""
        assert parse_beliefs("BELIEF: One thing.\n\nBELIEF: Another.\nREPLACES: none\n") == [
            Belief("Another.", None)
        ]

    def test_a_placeholder_is_not_a_belief(self):
        assert parse_beliefs("BELIEF: <the belief>\nREPLACES: none\n") == []

    def test_a_belief_with_no_words_is_discarded(self):
        assert parse_beliefs("BELIEF: ...\nREPLACES: none\n") == []

    def test_more_than_the_cap_is_refused_rather_than_truncated(self):
        text = "".join(
            f"BELIEF: Thing number {i}.\nREPLACES: none\n\n" for i in range(MAX_BELIEFS + 3)
        )

        assert parse_beliefs(text) == []


class TestApplyingThem:
    def test_a_named_line_is_replaced_in_place(self, brain):
        changed = apply_beliefs(
            brain, [Belief("Prefers a brief short enough to read standing up.", "Prefers short briefs.")]
        )

        assert changed == ["profile.md"]
        text = (brain.path / "profile.md").read_text()
        assert "read standing up" in text
        assert "Prefers short briefs." not in text

    def test_a_new_belief_is_appended(self, brain):
        changed = apply_beliefs(brain, [Belief("Reads on a phone first.", None)])

        assert changed == ["profile.md"]
        assert (brain.path / "profile.md").read_text().endswith("Reads on a phone first.\n")

    def test_a_line_that_is_not_there_is_appended_rather_than_guessed_at(self, brain):
        """Never delete a line the model did not actually name."""
        before = (brain.path / "profile.md").read_text()

        apply_beliefs(brain, [Belief("Reads on a phone.", "Something never written.")])

        after = (brain.path / "profile.md").read_text()
        assert before.strip() in after
        assert after.rstrip().endswith("Reads on a phone.")

    def test_an_ambiguous_line_is_appended_rather_than_one_of_them_overwritten(self, brain):
        (brain.path / "profile.md").write_text("# Profile\n\nTwice.\n\nTwice.\n")

        apply_beliefs(brain, [Belief("Once, clearly.", "Twice.")])

        text = (brain.path / "profile.md").read_text()
        assert text.count("Twice.") == 2
        assert "Once, clearly." in text

    def test_a_style_line_lands_in_the_style_guide(self, brain):
        changed = apply_beliefs(brain, [Belief("Never opens with a preamble.", "Direct sentences.")])

        assert changed == ["style-guide.md"]
        assert "preamble" in (brain.path / "style-guide.md").read_text()

    def test_nothing_proposed_changes_nothing(self, brain):
        before = (brain.path / "profile.md").read_text()

        assert apply_beliefs(brain, []) == []
        assert (brain.path / "profile.md").read_text() == before
