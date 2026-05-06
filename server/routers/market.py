from __future__ import annotations

import threading
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from server.models.backtest import KlineBar
from server.services.market_service import get_kline
from quant.data.updater import (
    list_cached_symbols,
    update_symbol,
    update_all,
    fetch_all_a_symbols,
    download_all_a,
    DataSource,
)

router = APIRouter(prefix="/api/market", tags=["market"])

# ── 全 A 下载状态 ──
_download_state: dict = {"running": False, "current": 0, "total": 0, "symbol": "", "result": None}
_download_lock = threading.Lock()


@router.get("/kline", response_model=list[KlineBar])
def api_kline(
    symbol: str = Query(..., description="股票代码"),
    start_date: str = Query("2023-01-01"),
    end_date: str = Query("2024-12-31"),
):
    return get_kline(symbol, start_date, end_date)


@router.get("/cache")
def api_cache_list():
    return list_cached_symbols()


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
