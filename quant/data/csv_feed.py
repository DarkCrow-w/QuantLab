from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

from quant.core.bar import Bar
from quant.core.events import MarketEvent
from .base import DataFeed


class CSVFeed(DataFeed):
    """CSV-based data feed for testing. Expects columns: dt,open,high,low,close,volume,amount."""

    def __init__(self, csv_dir: str | Path) -> None:
        self.csv_dir = Path(csv_dir)
        self._symbols: list[str] = []
        self._data: dict[str, pd.DataFrame] = {}
        self._dates: list[date] = []
        self._cursor: int = 0
        self._history: dict[str, list[Bar]] = defaultdict(list)

    def subscribe(self, symbols: list[str]) -> None:
        self._symbols = symbols
        all_dates: set[date] = set()
        for sym in symbols:
            path = self.csv_dir / f"{sym}.csv"
            df = pd.read_csv(path, parse_dates=["dt"])
            df["dt"] = df["dt"].dt.date
            df = df.sort_values("dt").reset_index(drop=True)
            self._data[sym] = df
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
                symbol=sym, dt=current_dt,
                open=float(r["open"]), high=float(r["high"]),
                low=float(r["low"]), close=float(r["close"]),
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
