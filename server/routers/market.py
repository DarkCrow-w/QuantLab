from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from quant.config import get_settings
from quant.data import INDICATORS
from quant.data.updater import (
    DataSource,
    derive_week_month,
    fetch_all_a_symbols,
    refresh_calendar,
    refresh_universe,
    update_universe,
)
from server.models.backtest import KlineBar
from server.services.data_job_service import get_data_job_manager
from server.services.market_service import (
    get_cache_status,
    get_calendar,
    get_indicator,
    get_kline,
    get_universe,
)

Freq = Literal["day", "week", "month"]
router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/kline", response_model=list[KlineBar])
def api_kline(
    symbol: str = Query(..., description="股票代码"),
    start_date: str = Query("2023-01-01"),
    end_date: str = Query("2024-12-31"),
    freq: Freq = Query("day"),
):
    return get_kline(symbol, start_date, end_date, freq=freq)


@router.get("/indicator/{name}")
def api_indicator(
    name: str,
    symbol: str = Query(...),
    start_date: str = Query("2023-01-01"),
    end_date: str = Query("2024-12-31"),
    freq: Freq = Query("day"),
):
    if name.upper() not in INDICATORS:
        raise HTTPException(status_code=404, detail=f"unknown indicator: {name}")
    return get_indicator(symbol, name, start_date, end_date, freq=freq)


@router.get("/indicators")
def api_indicators_list():
    return [
        {
            "name": name,
            "params": list(spec.params),
            "columns": list(spec.output_columns),
            "lookback": spec.lookback,
            "version": spec.version,
        }
        for name, spec in INDICATORS.items()
    ]


@router.get("/universe")
def api_universe(market: str | None = Query(None, description="SH/SZ/BJ")):
    return get_universe(market=market)


@router.get("/calendar")
def api_calendar(start: str | None = Query(None), end: str | None = Query(None)):
    return get_calendar(start=start, end=end)


@router.get("/cache")
def api_cache_list():
    from quant.data.updater import list_cached_symbols

    return list_cached_symbols()


@router.get("/cache/status")
def api_cache_status():
    return get_cache_status()


class UpdateRequest(BaseModel):
    symbols: list[str] | None = None
    source: DataSource = "tdx"
    workers: int | None = None
    materialize_indicators: bool = False


@router.post("/update")
def api_update(req: UpdateRequest = UpdateRequest()):
    """Queue cached-symbol updates; supplying symbols creates a focused job."""
    return get_data_job_manager().start(
        "update",
        source=req.source,
        symbols=req.symbols,
        workers=req.workers or get_settings().workers_for(req.source),
        materialize_indicators=req.materialize_indicators,
    )


@router.get("/stocks")
def api_stock_list(source: DataSource = Query("tdx")):
    return fetch_all_a_symbols(source=source)


class DownloadAllRequest(BaseModel):
    source: DataSource = "tdx"
    workers: int | None = None
    materialize_indicators: bool = False


@router.post("/download-all")
def api_download_all(req: DownloadAllRequest = DownloadAllRequest()):
    """Queue a resource-bounded whole-market download."""
    return get_data_job_manager().start(
        "download",
        source=req.source,
        workers=req.workers or get_settings().workers_for(req.source),
        materialize_indicators=req.materialize_indicators,
    )


@router.get("/download-all/progress")
def api_download_progress():
    """Compatibility endpoint backed by the unified job queue."""
    return _latest_job()


@router.get("/jobs/current")
def api_current_data_job():
    return _latest_job()


@router.get("/jobs/{job_id}")
def api_data_job(job_id: str):
    job = get_data_job_manager().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="data job not found")
    return job


@router.post("/jobs/{job_id}/pause")
def api_pause_data_job(job_id: str):
    result = get_data_job_manager().pause(job_id)
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="data job not found")
    if result["status"] == "invalid":
        raise HTTPException(status_code=409, detail="data job cannot be paused")
    return result


@router.post("/jobs/{job_id}/resume")
def api_resume_data_job(job_id: str):
    result = get_data_job_manager().resume(job_id)
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="data job not found")
    if result["status"] == "invalid":
        raise HTTPException(status_code=409, detail="data job cannot be resumed")
    return result


@router.post("/jobs/{job_id}/cancel")
def api_cancel_data_job(job_id: str):
    result = get_data_job_manager().cancel(job_id)
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="data job not found")
    if result["status"] == "invalid":
        raise HTTPException(status_code=409, detail="data job cannot be cancelled")
    return result


def _latest_job() -> dict:
    return get_data_job_manager().latest() or {
        "running": False,
        "status": "idle",
        "completed": 0,
        "total": 0,
        "percent": 0,
        "recent": [],
    }


class UpdateUniverseRequest(BaseModel):
    symbols: list[str] | None = None
    freq: Freq = "day"
    end_date: str | None = None
    workers: int | None = None
    force: bool = False
    materialize_indicators: bool = False


@router.post("/v2/update")
def api_v2_update(req: UpdateUniverseRequest = UpdateUniverseRequest()):
    report = update_universe(
        symbols=req.symbols,
        freq=req.freq,
        end_date=req.end_date,
        workers=req.workers or get_settings().tdx.workers,
        force=req.force,
        recompute_indicators=req.materialize_indicators,
    )
    return {
        "total": report.total,
        "updated": report.updated,
        "skipped": report.skipped,
        "failed": report.failed,
        "by_source": report.by_source,
        "errors": report.errors[:50],
        "elapsed_s": round(report.elapsed_s, 2),
    }


@router.post("/v2/resample")
def api_v2_resample(target_freq: Freq = Query("week")):
    if target_freq == "day":
        raise HTTPException(status_code=400, detail="target_freq must be week or month")
    report = derive_week_month(target_freq=target_freq)
    return {
        "freq": target_freq,
        "updated": report.updated,
        "failed": report.failed,
        "elapsed_s": round(report.elapsed_s, 2),
    }


@router.post("/v2/refresh-calendar")
def api_v2_refresh_calendar():
    return {"open_days": refresh_calendar()}


@router.post("/v2/refresh-universe")
def api_v2_refresh_universe(source: DataSource = Query("akshare")):
    from quant.data.feeds import AKShareSource, TDXSource, TushareSource

    sources = {
        "akshare": AKShareSource(),
        "tdx": TDXSource(),
        "tushare": TushareSource(),
    }
    selected = sources.get(source)
    if selected is None:
        raise HTTPException(status_code=400, detail=f"unsupported source: {source}")
    return {"symbols": refresh_universe(source=selected), "source": source}
