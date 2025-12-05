from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Position:
    """Tracks a single symbol position."""

    symbol: str
    quantity: int = 0
    avg_cost: float = 0.0  # per share, including commission

    @property
    def market_value(self) -> float:
        """Needs external price; returns cost-based value as fallback."""
        return self.quantity * self.avg_cost

    def update_on_fill(self, qty: int, price: float, commission: float) -> None:
        """Update position after a fill. qty > 0 = buy, qty < 0 = sell."""
        if qty > 0:
            total_cost = self.avg_cost * self.quantity + price * qty + commission
            self.quantity += qty
            self.avg_cost = total_cost / self.quantity if self.quantity else 0.0
        else:
            self.quantity += qty  # qty is negative
            if self.quantity <= 0:
                self.quantity = 0
                self.avg_cost = 0.0
