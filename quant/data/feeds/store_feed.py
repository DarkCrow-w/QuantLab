"""StoreFeed — DataFeed 实现，数据来自 ``DataStore``，回测引擎专用。

替代旧的 AKShareFeed/TDXFeed/TuShareFeed：
- 数据获取与回测解耦：先用 ``updater`` 把数据写入 ``DataStore``，再让 ``StoreFeed`` 迭代
- 通过 ``get_dataframe(symbol)`` 替代旧代码 ``feed._data[symbol]`` 的私有反射
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

import pandas as pd

from quant.core.bar import Bar
from quant.core.events import MarketEvent

from ..base import DataFeed
from .. import indicators as ind_mod
from ..schema import Freq
from ..schema import OHLCV_COLUMNS
from ..store import DataStore, get_store


class StoreFeed(DataFeed):
    """DataFeed 接口，数据后端为 ``DataStore``。"""

    def __init__(
        self,
        start_date: str | date,
        end_date: str | date,
        freq: Freq = "day",
        with_indicators: bool | list[str] = False,
        store: DataStore | None = None,
    ) -> None:
        self.start_date = _to_date(start_date)
        self.end_date = _to_date(end_date)
        self.freq = freq
        self.with_indicators = with_indicators
        self.store = store or get_store()
        self._symbols: list[str] = []
        self._data: dict[str, pd.DataFrame] = {}
        self._dates: list[date] = []
        self._cursor = 0
        self._history: dict[str, list[Bar]] = defaultdict(list)

    # ─── DataFeed API ────────────────────────────────────────────────────
    def subscribe(self, symbols: list[str]) -> None:
        self._symbols = list(symbols)
        columns: list[str] | None = list(OHLCV_COLUMNS)
        if self.with_indicators is True:
            columns = None
        elif isinstance(self.with_indicators, list):
            columns.extend(
                column
                for name in self.with_indicators
                for column in ind_mod.INDICATORS[name.upper()].output_columns
            )
        self._data = self.store.get_klines(
            self._symbols, freq=self.freq,
            start=self.start_date, end=self.end_date,
            with_indicators=self.with_indicators,
            columns=columns,
        )
        all_dates: set[date] = set()
        for df in self._data.values():
            if not df.empty:
                df.set_index("dt", drop=False, inplace=True)
                all_dates.update(df.index.tolist())
        self._dates = sorted(all_dates)
        self._cursor = 0
        self._history.clear()

    def has_more(self) -> bool:
        return self._cursor < len(self._dates)

    def update(self) -> MarketEvent | None:
        while self._cursor < len(self._dates):
            current = self._dates[self._cursor]
            self._cursor += 1
            bars: dict[str, Bar] = {}
            for sym in self._symbols:
                df = self._data.get(sym)
                if df is None or df.empty:
                    continue
                if current not in df.index:
                    continue
                r = df.loc[current]
                if isinstance(r, pd.DataFrame):
                    r = r.iloc[-1]
                bar = Bar(
                    symbol=sym, dt=current,
                    open=float(r["open"]), high=float(r["high"]),
                    low=float(r["low"]), close=float(r["close"]),
                    volume=float(r["volume"]),
                    amount=float(r.get("amount", 0.0)),
                )
                bars[sym] = bar
                self._history[sym].append(bar)
            if bars:
                return MarketEvent(dt=current, bars=bars)
        return None

    def get_latest_bars(self, symbol: str, n: int = 1) -> list[Bar]:
        history = self._history.get(symbol, [])
        return history[-n:] if n <= len(history) else list(history)

    # ─── 新增公开方法 — 替代 feed._data[sym] 反射 ──────────────────────────
    def get_dataframe(self, symbol: str) -> pd.DataFrame:
        df = self._data.get(symbol)
        if df is None:
            return pd.DataFrame()
        return df


def _to_date(v: str | date) -> date:
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))
