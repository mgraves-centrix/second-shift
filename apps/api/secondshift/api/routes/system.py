"""What this deployment is, and whether it is up.

The two routes with no capability behind them: one answers a process check, the
other reports which policies the Airlock will honor here and why any will not.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..context import Context, get_context
from ..mappers import capability_payload
from ..schemas import CapabilityResponse

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/capabilities", response_model=CapabilityResponse)
def capabilities(ctx: Context = Depends(get_context)) -> CapabilityResponse:
    """Every policy with its availability and reason. None are omitted."""
    return capability_payload(ctx.report)
