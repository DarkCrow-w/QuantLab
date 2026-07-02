from __future__ import annotations

from fastapi import APIRouter, Query

from server.services.strategy_sample_service import (
    VOLUME_PULLBACK_STRATEGY_ID,
    list_strategy_samples,
)

router = APIRouter(prefix="/api/strategy/samples", tags=["strategy-samples"])


@router.get("")
def api_strategy_samples(strategy: str | None = Query(VOLUME_PULLBACK_STRATEGY_ID)):
    return list_strategy_samples(strategy=strategy)
