from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.models.market import StrategyAsset, StrategyAssetDraft
from server.services.strategy_asset_service import get_strategy_asset_store

router = APIRouter(prefix="/api/strategy/assets", tags=["strategy-assets"])


@router.get("", response_model=list[StrategyAsset])
def api_list_strategy_assets():
    return get_strategy_asset_store().list()


@router.get("/{asset_id}", response_model=StrategyAsset)
def api_get_strategy_asset(asset_id: str):
    asset = get_strategy_asset_store().get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="strategy asset not found")
    return asset


@router.post("", response_model=StrategyAsset)
def api_create_strategy_asset(draft: StrategyAssetDraft):
    try:
        return get_strategy_asset_store().save(draft)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/{asset_id}", response_model=StrategyAsset)
def api_update_strategy_asset(asset_id: str, draft: StrategyAssetDraft):
    if get_strategy_asset_store().get(asset_id) is None:
        raise HTTPException(status_code=404, detail="strategy asset not found")
    try:
        return get_strategy_asset_store().save(draft, asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{asset_id}")
def api_delete_strategy_asset(asset_id: str):
    if not get_strategy_asset_store().delete(asset_id):
        raise HTTPException(status_code=404, detail="strategy asset not found")
    return {"status": "deleted"}
