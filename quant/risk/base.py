from __future__ import annotations

from abc import ABC, abstractmethod

from quant.core.events import SignalEvent, OrderEvent
from quant.core.portfolio import Portfolio


class RiskManager(ABC):
    @abstractmethod
    def approve(self, signal: SignalEvent, portfolio: Portfolio, price: float) -> OrderEvent | None:
        """Convert signal to order with position sizing, or reject."""
        ...
