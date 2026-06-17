from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from server.services.research_service import get_research_store

router = APIRouter(prefix="/api/research", tags=["research"])


class BacktestMetadataPatch(BaseModel):
    tags: list[str] | None = Field(default=None, max_length=12)
    note: str | None = Field(default=None, max_length=2000)
    favorite: bool | None = None


class ResearchReportRequest(BaseModel):
    run_ids: list[str] = Field(..., min_length=1, max_length=12)


@router.get("/summary")
def api_research_summary():
    return get_research_store().summary()


@router.get("/backtests")
def api_backtest_runs(
    limit: int = Query(50, ge=1, le=200),
    strategy: str | None = Query(None),
    favorite: bool | None = Query(None),
    tag: str | None = Query(None),
):
    return get_research_store().list_backtests(
        limit=limit,
        strategy=strategy,
        favorite=favorite,
        tag=tag,
    )


@router.get("/backtests/{run_id}")
def api_backtest_run(run_id: str):
    run = get_research_store().get_backtest(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="backtest run not found")
    return run


@router.patch("/backtests/{run_id}/metadata")
def api_update_backtest_metadata(run_id: str, patch: BacktestMetadataPatch):
    run = get_research_store().update_backtest_metadata(
        run_id,
        tags=patch.tags,
        note=patch.note,
        favorite=patch.favorite,
    )
    if run is None:
        raise HTTPException(status_code=404, detail="backtest run not found")
    return run


@router.post("/reports/backtests.md")
def api_backtest_report(req: ResearchReportRequest):
    report = get_research_store().build_backtest_report(req.run_ids)
    if report is None:
        raise HTTPException(status_code=404, detail="one or more backtest runs were not found")
    return Response(
        content=report,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="quantlab-research-report.md"'},
    )
