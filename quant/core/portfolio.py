from __future__ import annotations

from dataclasses import dataclass, field

from .bar import Bar
from .events import FillEvent
from .order import OrderSide
from .position import Position


@dataclass(slots=True)
class Portfolio:
    """Cash + positions + equity tracking."""

    initial_cash: float
    cash: float = 0.0
    positions: dict[str, Position] = field(default_factory=dict)
    total_commission: float = 0.0

    def __post_init__(self) -> None:
        if self.cash == 0.0:
            self.cash = self.initial_cash

    def get_position(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)
        return self.positions[symbol]

    def update_on_fill(self, fill: FillEvent) -> None:
        qty = fill.quantity if fill.side == OrderSide.BUY else -fill.quantity
        cost = fill.price * fill.quantity
        if fill.side == OrderSide.BUY:
            self.cash -= cost + fill.commission
        else:
            self.cash += cost - fill.commission
        self.total_commission += fill.commission
        self.get_position(fill.symbol).update_on_fill(qty, fill.price, fill.commission)

    def equity(self, prices: dict[str, float]) -> float:
        """Total equity = cash + sum(position_value at market price)."""
        position_value = sum(
            pos.quantity * prices.get(pos.symbol, pos.avg_cost)
            for pos in self.positions.values()
        )
        return self.cash + position_value

    def snapshot(self, prices: dict[str, float]) -> dict:
        return {
            "cash": self.cash,
            "equity": self.equity(prices),
            "positions": {
                s: {"qty": p.quantity, "avg_cost": p.avg_cost}
                for s, p in self.positions.items()
                if p.quantity > 0
            },
            "total_commission": self.total_commission,
        }
