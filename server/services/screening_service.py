from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import pandas as pd

from quant.core.bar import Bar
from quant.core.events import SignalEvent
from quant.core.events import OrderSide
from quant.data.cache import CACHE_DIR, load_cache
from quant.strategy.base import Context

from server.models.screening import ScreenMatch, ScreenRequest, ScreenResult
from server.services.backtest_service import STRATEGY_REGISTRY

_EMPTY_PORTFOLIO = {"positions": {}, "cash": 0, "equity": 0}


def _screen_symbol(strategy_cls, params: dict, bars: list[Bar], symbol: str) -> SignalEvent | None:
    """对单只股票回放策略，返回最后一根K线的 BUY 信号（如有）。"""
    strategy = strategy_cls(params=params)
    history: list[Bar] = []
    last_signals: list[SignalEvent] = []

    for bar in bars:
        history.append(bar)
        ctx = Context(
            bars={symbol: bar},
            history={symbol: list(history)},
            portfolio_snapshot=_EMPTY_PORTFOLIO,
            current_date=bar.dt,
        )
        last_signals = strategy.on_bar(ctx)

    for sig in last_signals:
        if sig.direction == OrderSide.BUY:
            return sig
    return None


def _process_symbol(
    symbol: str,
    strategy_cls,
    params: dict,
    scan_dt: date,
    lookback: int,
) -> ScreenMatch | None:
    """加载缓存并筛选单只股票。"""
    df = load_cache(symbol)
    if df is None or df.empty:
        return None

    # 过滤到 scan_date
    df = df[df["dt"] <= scan_dt].sort_values("dt")
    df = df.tail(lookback)

    if len(df) < 30:
        return None

    bars = [
        Bar(
            symbol=symbol,
            dt=row.dt,
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=float(row.volume),
            amount=float(getattr(row, "amount", 0)),
        )
        for row in df.itertuples(index=False)
    ]

    sig = _screen_symbol(strategy_cls, params, bars, symbol)
    if sig is None:
        return None

    last_bar = bars[-1]
    return ScreenMatch(
        symbol=symbol,
        signal_date=str(sig.dt),
        close=round(last_bar.close, 2),
        volume=last_bar.volume,
        amount=last_bar.amount,
        strength=sig.strength,
    )


def run_screening(req: ScreenRequest) -> ScreenResult:
    t0 = time.time()

    entry = STRATEGY_REGISTRY.get(req.strategy)
    if entry is None:
        raise ValueError(f"Unknown strategy: {req.strategy}")

    strategy_cls = entry["cls"]
    scan_dt = date.fromisoformat(req.scan_date) if req.scan_date else date.today()
    params = req.strategy_params or {}

    symbols = sorted(p.stem for p in CACHE_DIR.glob("*.parquet"))

    matches: list[ScreenMatch] = []

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(_process_symbol, sym, strategy_cls, params, scan_dt, req.lookback): sym
            for sym in symbols
        }
        for fut in as_completed(futures):
            try:
                result = fut.result()
                if result is not None:
                    matches.append(result)
            except Exception:
                pass

    matches.sort(key=lambda m: m.strength, reverse=True)

    return ScreenResult(
        strategy=req.strategy,
        scan_date=str(scan_dt),
        total_scanned=len(symbols),
        matches=matches,
        elapsed_seconds=round(time.time() - t0, 2),
    )
