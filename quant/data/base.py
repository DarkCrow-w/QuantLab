from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from quant.core.bar import Bar
from quant.core.events import MarketEvent


class DataFeed(ABC):
    """Abstract data feed interface."""

    @abstractmethod
    def subscribe(self, symbols: list[str]) -> None:
        """Register symbols to track."""

    @abstractmethod
    def update(self) -> MarketEvent | None:
        """Advance one bar and return MarketEvent, or None if exhausted."""

    @abstractmethod
    def get_latest_bars(self, symbol: str, n: int = 1) -> list[Bar]:
        """Return the last N bars for symbol (most recent last)."""

    @abstractmethod
    def has_more(self) -> bool:
        """Whether there is more data to iterate."""

    def get_dataframe(self, symbol: str) -> pd.DataFrame:
        """Return the cached DataFrame for ``symbol`` (empty if unknown).

        Default implementation reads from ``self._data`` for legacy feeds that
        still use that attribute. Replaces direct ``feed._data[symbol]`` access.
        """
        data = getattr(self, "_data", None)
        if data is None:
            return pd.DataFrame()
        df = data.get(symbol)
        return df if df is not None else pd.DataFrame()
