from __future__ import annotations

from abc import ABC, abstractmethod

from quant.core.events import OrderEvent, FillEvent


class Broker(ABC):
    @abstractmethod
    def submit_order(self, order: OrderEvent, fill_price: float) -> FillEvent:
        """Submit order and return fill."""
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        ...
