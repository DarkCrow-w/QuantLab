from __future__ import annotations

from fastapi import APIRouter

from server.services.trading_service import get_trading_status

router = APIRouter(prefix="/api/trading", tags=["trading"])


@router.get("/status")
def api_trading_status():
    return get_trading_status()
