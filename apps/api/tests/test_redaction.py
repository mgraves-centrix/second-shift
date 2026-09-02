"""The leak test. It is the reason `research` exists as a separate capability.

**The corpus below is synthetic and that is a limitation, not a choice.**
`docs/prompts/RESEARCH.md` says to build this list from the four real entries in
the database and the brain's `profile.md`. Neither was reachable when this
shipped: the development container's database holds zero entries and
`../second-shift-brain` is absent — both live on the always-on machine. The real
subject-authored text that *is* in the repository, `config/evals/candidates.md`,
is pre-sanitized because the repository is public and
`scripts/check-no-environment.sh` enforces it, so a redaction test against it
would pass with redaction deleted.

So each entry here is constructed to carry exactly one leak category, and the
names in them are fictional. **Re-running this against the real four is still
owed** — it is the check this substitute cannot perform.

The mutation was run: replacing `build_query`'s body with `return text` turns
`test_no_query_carries_a_distinctive_phrase_from_its_entry` red on every row.
"""

from __future__ import annotations

import inspect

import pytest

from secondshift.airlock.redact import MAX_TERMS, build_query

#: One constructed entry per leak category, and the thing that must not survive.
#: The third column is what a reader should be able to check by eye.
LEAK_CORPUS: list[tuple[str, str, str]] = [
    (
        "named third party",
        "Build an onboarding flow for Northwind Health that survives their "
        "compliance review.",
        "Northwind",
    ),
    (
        "employer",
        "How does Contoso handle on-call rotations without burning people out?",
        "Contoso",
    ),
    (
        "unreleased codename",
        "The pricing page for Project Halyard needs to explain tiering better.",
        "Halyard",
    ),
    (
        "person by name",
        "Figure out how to give Priya feedback about missed deadlines.",
        "Priya",
    ),
    (
        "health specifics",
        "Managing standups around my chemo schedule without telling everyone.",
        "chemo",
    ),
    (
        "credential-shaped",
        "I keep pasting sk-live-9f2b7c1d4e8a0badc0ffee into my notes by accident.",
        "sk-live-9f2b7c1d4e8a0badc0ffee",
    ),
    (
        "contact and host",
        "Reach me at person@example.com or on box.tailnet-name.ts.net.",
        "tailnet-name",
    ),
    (
        "legal and financial",
        "Should I take the severance or push back on the redundancy terms?",
        "severance",
    ),
]

#: Phrases distinctive enough to identify the writer even with every name gone.
#: Category 8 — the one no filter can address, and the reason redaction is
#: construction rather than filtering.
DISTINCTIVE_PHRASES = [
    (
        "Build an onboarding flow for Northwind Health that survives their "
        "compliance review.",
        "survives their compliance review",
    ),
    (
        "How does Contoso handle on-call rotations without burning people out?",
        "without burning people out",
    ),
    (
        "Figure out how to give Priya feedback about missed deadlines.",
        "give Priya feedback about missed",
    ),
]


class TestTheLeakList:
    @pytest.mark.parametrize(
        ("category", "entry", "must_not_survive"),
        LEAK_CORPUS,
        ids=[c for c, _, _ in LEAK_CORPUS],
    )
    def test_the_identifying_material_does_not_reach_the_query(
        self, category, entry, must_not_survive
    ):
        query = build_query(entry)

        assert must_not_survive.lower() not in query.lower(), (
            f"{category}: {must_not_survive!r} survived into {query!r}"
        )

    @pytest.mark.parametrize(("entry", "phrase"), DISTINCTIVE_PHRASES)
    def test_no_query_carries_a_distinctive_phrase_from_its_entry(
        self, entry, phrase
    ):
        """Category 8, and the load-bearing assertion.

        Six distinctive words identify a person's writing without containing a
        single name. This is what fails when `build_query` returns its input,
        and it is why the query is constructed rather than filtered.
        """
        query = build_query(entry)

        assert phrase.lower() not in query.lower()

    def test_no_query_reproduces_a_run_of_its_source(self):
        """Stronger than the phrase list: no four consecutive words of any
        corpus entry may appear in its query, whichever four they are."""
        for _, entry, _ in LEAK_CORPUS:
            query = build_query(entry).lower()
            words = entry.lower().replace(".", "").replace("?", "").split()
            runs = [" ".join(words[i : i + 4]) for i in range(len(words) - 3)]

            surviving = [r for r in runs if r in query]
            assert not surviving, f"{surviving} survived into {query!r}"

    def test_the_queries_are_still_worth_searching(self):
        """A redactor that returns nothing passes every test above.

        This is the counterweight: the queries have to retain enough topic to be
        a search rather than a shrug. Not a quality bar — a floor.

        `contact and host` is excluded, and the exclusion is the finding: that
        entry is contact details rather than an idea, so almost nothing survives
        and almost nothing should. It yields a single term. **A caller must treat
        a thin query as "there is nothing to search here" and skip the call** —
        never as a reason to fall back toward the raw text, which is the one move
        that would undo this whole module.
        """
        for category, entry, _ in LEAK_CORPUS:
            if category == "contact and host":
                continue
            query = build_query(entry)
            assert len(query.split()) >= 2, f"{category}: {query!r} is not a query"

    def test_an_entry_that_is_only_contact_details_yields_almost_nothing(self):
        """Pinned deliberately: the caller's skip threshold depends on it."""
        entry = "Reach me at person@example.com or on box.tailnet-name.ts.net."

        assert len(build_query(entry).split()) < 2


class TestRedactionCannotBeDisabled:
    def test_build_query_takes_exactly_one_parameter(self):
        """Principle 2 names a redaction that configuration can disable as a
        violation *even when it defaults to on*. So the guard is not a safe
        default — it is that there is nowhere to put an unsafe one.

        This test is what makes that enforceable rather than remembered.
        """
        signature = inspect.signature(build_query)

        assert list(signature.parameters) == ["text"], (
            "build_query grew a parameter. If it selects a weaker path, that is "
            "a constitution violation regardless of its default."
        )

    def test_no_module_level_switch_governs_redaction(self):
        """A module constant read at call time is the same violation wearing a
        different hat."""
        from secondshift.airlock import redact

        switches = [
            n
            for n in dir(redact)
            if n.isupper() and isinstance(getattr(redact, n), bool)
        ]
        assert switches == []


class TestWhatEarnsItsWayIn:
    def test_a_sentence_initial_capital_is_not_treated_as_a_name(self):
        """Without this the first word of every entry is dropped — and it is
        usually the verb the whole search is about."""
        assert "build" in build_query("Build a better deployment pipeline.")

    def test_a_mid_sentence_capital_is_dropped_without_asking_what_it_is(self):
        """The property that makes an unknown codename as safe as a known one."""
        assert "wingspan" not in build_query("Ship the Wingspan integration.").lower()

    def test_an_unknown_proper_noun_is_as_safe_as_a_known_one(self):
        for name in ("Zylotrix", "Quandrel", "Bexforth"):
            assert name.lower() not in build_query(f"Plan the {name} migration.").lower()

    def test_the_query_is_capped(self):
        long_entry = " ".join(f"topic{i}" for i in range(50))

        assert len(build_query(long_entry).split()) <= MAX_TERMS

    def test_a_duplicate_term_appears_once(self):
        assert build_query("deployment deployment deployment pipeline").split() == [
            "deployment",
            "pipeline",
        ]

    def test_empty_text_yields_an_empty_query_rather_than_raising(self):
        assert build_query("") == ""

    def test_a_text_of_only_stopwords_yields_an_empty_query(self):
        """Which the caller must treat as "nothing searchable here", not as a
        reason to fall back to the raw text."""
        assert build_query("the and or but if of to") == ""
