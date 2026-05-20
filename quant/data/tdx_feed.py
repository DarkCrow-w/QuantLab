"""通达信(TDX)数据源 — 通过 pytdx 连接行情服务器获取日线数据。"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

import pandas as pd
from loguru import logger

from quant.core.bar import Bar
from quant.core.events import MarketEvent
from .base import DataFeed
from .cache import load_cache, save_cache
from .feeds.tdx import TDXSource


def _fetch_daily(symbol: str, start: str, end: str) -> pd.DataFrame:
    """从通达信服务器获取日线数据。

    Args:
        symbol: 股票代码, e.g. "600519"
        start: 开始日期, e.g. "20230101"
        end: 结束日期, e.g. "20261231"

    Returns:
        标准列名的 DataFrame: dt, open, high, low, close, volume, amount
    """
    logger.info(f"Fetching {symbol} from TDX ({start} ~ {end})")
    return TDXSource().fetch_daily(symbol, start, end)


class TDXFeed(DataFeed):
    """Daily-bar data feed backed by 通达信 with Parquet caching."""

    def __init__(self, start_date: str, end_date: str, use_cache: bool = True) -> None:
        self.start_date = start_date
        self.end_date = end_date
        self.use_cache = use_cache
        self._symbols: list[str] = []
        self._data: dict[str, pd.DataFrame] = {}
        self._dates: list[date] = []
        self._cursor: int = 0
        self._history: dict[str, list[Bar]] = defaultdict(list)

    def subscribe(self, symbols: list[str]) -> None:
        self._symbols = symbols
        for sym in symbols:
            df = None
            if self.use_cache:
                df = load_cache(sym)
                if df is not None:
                    df = df[(df["dt"] >= date.fromisoformat(self.start_date))
                            & (df["dt"] <= date.fromisoformat(self.end_date))]
                    if len(df) == 0:
                        df = None
            if df is None:
                df = _fetch_daily(
                    sym,
                    self.start_date.replace("-", ""),
                    self.end_date.replace("-", ""),
                )
                if self.use_cache:
                    save_cache(sym, df)
            self._data[sym] = df.reset_index(drop=True)
            logger.info(f"Subscribed {sym}: {len(df)} bars")

        all_dates: set[date] = set()
        for df in self._data.values():
            all_dates.update(df["dt"].tolist())
        self._dates = sorted(all_dates)
        self._cursor = 0

    def has_more(self) -> bool:
        return self._cursor < len(self._dates)

    def update(self) -> MarketEvent | None:
        if not self.has_more():
            return None
        current_dt = self._dates[self._cursor]
        self._cursor += 1
        bars: dict[str, Bar] = {}
        for sym in self._symbols:
            df = self._data[sym]
            row = df[df["dt"] == current_dt]
            if row.empty:
                continue
            r = row.iloc[0]
            bar = Bar(
                symbol=sym,
                dt=current_dt,
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r["volume"]),
                amount=float(r.get("amount", 0)),
            )
            bars[sym] = bar
            self._history[sym].append(bar)
        if not bars:
            return self.update()
        return MarketEvent(dt=current_dt, bars=bars)

    def get_latest_bars(self, symbol: str, n: int = 1) -> list[Bar]:
        history = self._history.get(symbol, [])
        return history[-n:] if n <= len(history) else list(history)
