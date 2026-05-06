from __future__ import annotations

from loguru import logger

from quant.core.events import SignalEvent, OrderEvent
from quant.core.order import OrderSide, OrderType
from quant.core.portfolio import Portfolio
from .base import RiskManager


class BasicRiskManager(RiskManager):
    """Fixed-fraction position sizing + max drawdown circuit breaker."""

    def __init__(
        self,
        max_position_pct: float = 0.3,
        max_drawdown: float = 0.2,
    ) -> None:
        self.max_position_pct = max_position_pct
        self.max_drawdown = max_drawdown
        self._peak_equity: float = 0.0

    def approve(self, signal: SignalEvent, portfolio: Portfolio, price: float) -> OrderEvent | None:
        equity = portfolio.equity({signal.symbol: price})
        self._peak_equity = max(self._peak_equity, equity)

        # Drawdown circuit breaker
        if self._peak_equity > 0:
            dd = (self._peak_equity - equity) / self._peak_equity
            if dd >= self.max_drawdown:
                logger.warning(f"Drawdown {dd:.2%} >= {self.max_drawdown:.2%}, rejecting signal")
                return None

        if signal.direction == OrderSide.BUY:
            # Position sizing: allocate max_position_pct * equity * strength
            alloc = equity * self.max_position_pct * signal.strength
            raw_qty = int(alloc / price)
            # A股最小交易单位100股
            qty = (raw_qty // 100) * 100
            if qty <= 0:
                logger.debug(f"Computed qty=0 for {signal.symbol}, skipping")
                return None
            return OrderEvent(
                symbol=signal.symbol,
                dt=signal.dt,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=qty,
            )
        else:
            # Sell: strength=1.0 liquidate full, <1.0 partial
            pos = portfolio.get_position(signal.symbol)
            if pos.quantity <= 0:
                return None
            if signal.strength < 1.0:
                raw_qty = int(pos.quantity * signal.strength)
                qty = (raw_qty // 100) * 100
                if qty <= 0:
                    qty = pos.quantity  # 不足一手则全卖
            else:
                qty = pos.quantity
            return OrderEvent(
                symbol=signal.symbol,
                dt=signal.dt,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=qty,
            )
