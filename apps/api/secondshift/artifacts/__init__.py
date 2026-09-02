"""Artifacts: files you can open, and the variant groups the critic ranks.

The middle term of "idea in, artifact out, memory in between." A row here always
describes bytes on disk, hashed after the write rather than before, and a rank
is always something a critic produced rather than the order things happened to
be generated in.
"""

from .store import (
    ENV_ARTIFACTS,
    VARIANT_KINDS,
    ArtifactWriteFailed,
    WrittenArtifact,
    artifact_root,
    default_root,
    relative_path,
    verify,
    write_artifact,
)
from .variants import RankingRefused, VariantSet, parse_ordering, rank_group, write_variants

__all__ = [
    "ArtifactWriteFailed",
    "ENV_ARTIFACTS",
    "RankingRefused",
    "VARIANT_KINDS",
    "VariantSet",
    "WrittenArtifact",
    "artifact_root",
    "default_root",
    "parse_ordering",
    "rank_group",
    "relative_path",
    "verify",
    "write_artifact",
    "write_variants",
]
