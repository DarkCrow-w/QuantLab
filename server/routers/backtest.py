from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.models.backtest import BacktestRequest, BacktestResult
from server.services.backtest_service import run_backtest

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("/run", response_model=BacktestResult)
def api_run_backtest(req: BacktestRequest):
    try:
        return run_backtest(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
