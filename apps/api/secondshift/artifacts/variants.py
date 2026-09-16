"""Variant groups, and the ranking that is never the generation order.

Three fields, three writers, on purpose:

    variant_group   the writer, once per fan-out    a fresh id
    variant_index   the writer, per variant         enumeration order
    variant_rank    the ranker, afterward           the critic's ordering

`write_variants` cannot set a rank because at write time no rank exists — the
critic has not spoken. That is structural rather than a rule somebody has to
remember, and it is what stops the ranks from quietly becoming the indices.

The synthetic night generates shuffled ranks precisely so a renderer that
assumes rank equals index is wrong on that data. Anything reading these fields
has to survive it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ..db.connection import now_ms
from ..db.ids import new_ulid
from ..db.repository import Repository
from .store import VARIANT_KINDS, ArtifactWriteFailed, WrittenArtifact, write_artifact

#: Indices as the critic writes them. Deliberately narrow: bare integers
#: anywhere in prose would match a token count or a year.
_ORDERING = re.compile(r"\bvariant\s+(\d+)", re.I)


class RankingRefused(ValueError):
    """The critic's ordering does not cover exactly this group's variants.

    Refused wholesale rather than applied in part: a group with three of five
    ranked reads as a complete ranking to anything that sorts by rank and puts
    nulls last, so "ranked" stays a property of the group.
    """


@dataclass(frozen=True, slots=True)
class VariantSet:
    """One fan-out: the group id and what actually landed."""

    group: str
    written: list[WrittenArtifact]
    #: Indices whose generation failed. Their siblings still exist — a fan-out
    #: where one variant's failure loses the other four is the principle-3
    #: violation named in the prompt.
    failed: list[int]


def parse_ordering(text: str) -> list[int]:
    """Variant indices in the order the critic ranked them, best first.

    Duplicates are preserved rather than deduplicated: a critic that named the
    same variant twice produced an ordering nobody should apply, and silently
    collapsing it would hide that.
    """
    return [int(m) for m in _ORDERING.findall(text)]


def write_variants(
    repo: Repository,
    *,
    run_id: str,
    entry_id: str,
    night_of: str,
    stage: str,
    kind: str,
    contents: Sequence[str | None],
    produced_by_invocation_id: str | None = None,
    is_synthetic: bool = False,
    root: Path | None = None,
    group: str | None = None,
) -> VariantSet:
    """Write a fan-out's variants. A `None` content means that one failed.

    Each variant is written and recorded as it completes, so a later failure
    never removes an earlier success.
    """
    if kind not in VARIANT_KINDS:
        raise ValueError(f"{kind!r} is not a variant kind; use write_artifact")

    group_id = group or new_ulid(now_ms())
    written: list[WrittenArtifact] = []
    failed: list[int] = []
    for index, content in enumerate(contents):
        if content is None:
            failed.append(index)
            continue
        try:
            written.append(
                write_artifact(
                    repo,
                    run_id=run_id,
                    entry_id=entry_id,
                    night_of=night_of,
                    stage=stage,
                    kind=kind,
                    content=content,
                    produced_by_invocation_id=produced_by_invocation_id,
                    variant_group=group_id,
                    variant_index=index,
                    is_synthetic=is_synthetic,
                    root=root,
                )
            )
        except ArtifactWriteFailed:
            failed.append(index)
    return VariantSet(group=group_id, written=written, failed=failed)


def rank_group(repo: Repository, group: str, ordering: Sequence[int]) -> None:
    """Apply a critic's ordering to a variant group. All or nothing.

    `ordering` is best first, so the first index named becomes rank 1.

    Refuses where the ordering does not cover exactly the indices in the group.
    Writing what parsed and leaving the rest null would produce a group that
    reads as fully ranked to anything sorting by rank, which is worse than one
    that is honestly unranked.
    """
    rows = repo.connection.execute(
        "SELECT id, variant_index FROM artifacts WHERE variant_group = ?", (group,)
    ).fetchall()
    if not rows:
        raise RankingRefused(f"no variants exist in group {group!r}")

    present = {r["variant_index"] for r in rows}
    named = list(ordering)
    if len(named) != len(set(named)) or set(named) != present:
        raise RankingRefused(
            f"the critic's ordering {named} does not cover exactly the variants "
            f"in group {group!r} ({sorted(present)}) — refusing to rank the "
            "group in part, because a partly ranked group reads as a fully "
            "ranked one to anything that sorts by rank"
        )

    by_index = {r["variant_index"]: r["id"] for r in rows}
    for rank, index in enumerate(named, start=1):
        repo.connection.execute(
            "UPDATE artifacts SET variant_rank = ? WHERE id = ?",
            (rank, by_index[index]),
        )
