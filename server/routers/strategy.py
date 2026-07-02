from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.models.market import StrategyInfo
from server.services.backtest_service import STRATEGY_REGISTRY, get_strategy_list
from server.services.strategy_asset_service import get_strategy_asset_store
from server.services.strategy_visibility_service import get_strategy_visibility_store

router = APIRouter(prefix="/api/strategy", tags=["strategy"])


@router.get("/list", response_model=list[StrategyInfo])
def api_strategy_list():
    return get_strategy_list()


@router.delete("/list/{strategy_name}")
def api_delete_basic_strategy_template(strategy_name: str):
    if strategy_name not in STRATEGY_REGISTRY:
        raise HTTPException(status_code=404, detail="strategy template not found")
    get_strategy_visibility_store().hide(strategy_name)
    get_strategy_asset_store().delete(f"builtin_{strategy_name}")
    return {"status": "deleted"}
