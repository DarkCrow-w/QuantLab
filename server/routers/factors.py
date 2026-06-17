from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.models.factor import (
    FactorMiningRequest,
    FactorMiningResult,
    ManagedFactor,
    ManagedFactorDraft,
)
from server.services.factor_service import get_factor_store, mine_factors

router = APIRouter(prefix="/api/factors", tags=["factors"])


@router.get("", response_model=list[ManagedFactor])
def api_list_factors():
    return get_factor_store().list()


@router.post("", response_model=ManagedFactor)
def api_create_factor(draft: ManagedFactorDraft):
    return get_factor_store().save(draft)


@router.put("/{factor_id}", response_model=ManagedFactor)
def api_update_factor(factor_id: str, draft: ManagedFactorDraft):
    if get_factor_store().get(factor_id) is None:
        raise HTTPException(status_code=404, detail="factor not found")
    return get_factor_store().save(draft, factor_id)


@router.delete("/{factor_id}")
def api_delete_factor(factor_id: str):
    try:
        deleted = get_factor_store().delete(factor_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=404, detail="factor not found")
    return {"status": "deleted"}


@router.post("/mine", response_model=FactorMiningResult)
def api_mine_factors(req: FactorMiningRequest):
    return mine_factors(req)
