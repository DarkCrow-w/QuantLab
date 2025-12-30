from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from quant.core.bar import Bar
from quant.core.events import SignalEvent


@dataclass(frozen=True)
class Context:
    """Read-only context passed to strategy on each bar."""

    bars: dict[str, Bar]  # current bar per symbol
    history: dict[str, list[Bar]]  # symbol -> historical bars (including current)
    portfolio_snapshot: dict  # from Portfolio.snapshot()
    current_date: object = None  # date

    def latest(self, symbol: str, n: int = 1) -> list[Bar]:
        h = self.history.get(symbol, [])
        return h[-n:] if n <= len(h) else list(h)

    def closes(self, symbol: str, n: int = 0) -> list[float]:
        """Return list of close prices. n=0 means all available."""
        h = self.history.get(symbol, [])
        src = h[-n:] if n > 0 else h
        return [b.close for b in src]


class Strategy(ABC):
    """Base strategy. Subclass and implement on_bar."""

    def __init__(self, params: dict | None = None) -> None:
        self.params = params or {}

    @abstractmethod
    def on_bar(self, ctx: Context) -> list[SignalEvent]:
        """Process new bar data and return signals."""
        ...
