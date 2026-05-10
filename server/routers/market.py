from __future__ import annotations

import threading
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from server.models.backtest import KlineBar
from server.services.market_service import (
    get_cache_status,
    get_calendar,
    get_indicator,
    get_kline,
    get_universe,
)
from quant.data import INDICATORS
from quant.data.updater import (
    DataSource,
    derive_week_month,
    download_all_a,
    fetch_all_a_symbols,
    list_cached_symbols,
    refresh_calendar,
    refresh_universe,
    update_all,
    update_symbol,
    update_universe,
)

Freq = Literal["day", "week", "month"]

router = APIRouter(prefix="/api/market", tags=["market"])

# ── 全 A 下载状态 ──
_download_state: dict = {"running": False, "current": 0, "total": 0, "symbol": "", "result": None}
_download_lock = threading.Lock()


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
    """返回所有支持的指标 + 默认参数 + 输出列名。"""
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
def api_universe(market: str | None = Query(None, description="SH/SZ/BJ; 为空返回全部")):
    return get_universe(market=market)


@router.get("/calendar")
def api_calendar(
    start: str | None = Query(None),
    end: str | None = Query(None),
):
    return get_calendar(start=start, end=end)


@router.get("/cache")
def api_cache_list():
    return list_cached_symbols()


@router.get("/cache/status")
def api_cache_status():
    """返回 last_update.parquet 内容，比 ``/cache`` 更详细（带 last_dt/source/ts_updated）。"""
    return get_cache_status()


class UpdateRequest(BaseModel):
    symbols: list[str] | None = None
    source: DataSource = "tushare"


@router.post("/update")
def api_update(req: UpdateRequest = UpdateRequest()):
    if req.symbols:
        return [update_symbol(s, source=req.source) for s in req.symbols]
    return update_all(source=req.source)


@router.get("/stocks")
def api_stock_list(source: DataSource = Query("tushare", description="数据源: tushare 或 tdx")):
    """获取全部 A 股上市股票列表。"""
    return fetch_all_a_symbols(source=source)


class DownloadAllRequest(BaseModel):
    source: DataSource = "tushare"


@router.post("/download-all")
def api_download_all(req: DownloadAllRequest = DownloadAllRequest()):
    """启动全 A 股数据下载（后台执行）。"""
    with _download_lock:
        if _download_state["running"]:
            return {"status": "already_running", **_download_state}
        _download_state.update(running=True, current=0, total=0, symbol="", result=None)

    def _run():
        def on_progress(current: int, total: int, symbol: str, status: str):
            _download_state.update(current=current, total=total, symbol=symbol)

        try:
            result = download_all_a(delay=0.35, on_progress=on_progress, source=req.source)
            _download_state["result"] = result
        except Exception as e:
            _download_state["result"] = {"error": str(e)}
        finally:
            _download_state["running"] = False

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started"}


@router.get("/download-all/progress")
def api_download_progress():
    """查询全 A 下载进度。"""
    return dict(_download_state)


# ── v2 新端点：DataStore 后端，源回退链 + 指标自动重算 ─────────────────────
class UpdateUniverseRequest(BaseModel):
    symbols: list[str] | None = None
    freq: Freq = "day"
    end_date: str | None = None
    workers: int = 8
    force: bool = False


@router.post("/v2/update")
def api_v2_update(req: UpdateUniverseRequest = UpdateUniverseRequest()):
    """v2 增量更新（DataStore 后端，TDX→AKShare→Tushare 回退链）。"""
    report = update_universe(
        symbols=req.symbols, freq=req.freq, end_date=req.end_date,
        workers=req.workers, force=req.force,
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
    """从 day 重采样得到 week/month。"""
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
    n = refresh_calendar()
    return {"open_days": n}


@router.post("/v2/refresh-universe")
def api_v2_refresh_universe(source: DataSource = Query("akshare")):
    from quant.data.feeds import AKShareSource, TDXSource, TushareSource
    src_map = {"akshare": AKShareSource(), "tdx": TDXSource(), "tushare": TushareSource()}
    src = src_map.get(source)
    if src is None:
        raise HTTPException(status_code=400, detail=f"unsupported source: {source}")
    n = refresh_universe(source=src)
    return {"symbols": n, "source": source}
