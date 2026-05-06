from __future__ import annotations

from fastapi import APIRouter

from server.models.market import StrategyInfo
from server.services.backtest_service import get_strategy_list

router = APIRouter(prefix="/api/strategy", tags=["strategy"])


@router.get("/list", response_model=list[StrategyInfo])
def api_strategy_list():
    return get_strategy_list()
