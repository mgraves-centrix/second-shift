"""Serving what the night produced.

The URL carries an id and never a path, so traversal is not a check that can be
forgotten — it cannot be expressed.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from ...artifacts.store import artifact_root
from ..context import Context, get_context

#: Content types for what the night writes. From the suffix rather than sniffed:
#: sniffing is how a renderer ends up deciding that somebody's idea is HTML.
_MEDIA_TYPES = {
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".json": "application/json",
}

router = APIRouter()


@router.get("/artifacts/{artifact_id}")
def artifact(artifact_id: str, ctx: Context = Depends(get_context)) -> Response:
    """One artifact's content, by identity.

    "Idea in, artifact out" is the whole claim and until now the artifact
    could not be opened: the night wrote files and nothing served them, so
    every interface listed paths a reader had no way to follow.

    The URL carries an id and never a path, so traversal is not a check that
    can be forgotten — it cannot be expressed. The stored path is relative to
    the configured root, and the resolved file is still required to sit under
    it, because a row is data and `..` in one would otherwise be obeyed.

    `model_call_payloads` is not reachable from here and this response has no
    field it could travel in — the same structural argument `/events/{id}`
    makes. That table is local-only content by construction.
    """
    row = ctx.repo.get_artifact(artifact_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown artifact {artifact_id!r}",
        )

    root = artifact_root().resolve()
    target = (root / row["path"]).resolve()
    if not target.is_relative_to(root):
        # The row escaped its root. Refused rather than served: a stored
        # path is data, and this is the one place it becomes a filesystem
        # read.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown artifact {artifact_id!r}",
        )
    try:
        body = target.read_bytes()
    except OSError:
        # A row naming a file that is not there is a defect, and answering
        # it with an empty 200 would hide one. The seeded night writes rows
        # with no bytes behind them, and that is exactly the case this must
        # not paper over.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"artifact {artifact_id!r} has no file at its recorded path",
        ) from None

    return Response(
        content=body,
        media_type=_MEDIA_TYPES.get(target.suffix, "application/octet-stream"),
    )
