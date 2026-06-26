from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from server.models.backtest import BacktestGridRequest, BacktestGridResult, BacktestRequest, BacktestResult
from server.services.backtest_service import run_backtest, run_backtest_grid
from server.services.research_service import get_research_store

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("/run", response_model=BacktestResult)
def api_run_backtest(
    req: BacktestRequest,
    save: bool = Query(True, description="Persist successful run to research assets"),
):
    try:
        result = run_backtest(req)
        if save:
            get_research_store().save_backtest(req, result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/grid", response_model=BacktestGridResult)
def api_run_backtest_grid(
    req: BacktestGridRequest,
    save: bool = Query(True, description="Persist completed grid runs to research assets"),
):
    try:
        save_result = None

        if save:
            store = get_research_store()

            def save_result(item_req: BacktestRequest, result: BacktestResult) -> str | None:
                saved = store.save_backtest(item_req, result)
                return saved.get("id")

        return run_backtest_grid(req, save_result=save_result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
