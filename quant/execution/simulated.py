from __future__ import annotations

from loguru import logger

from quant.core.events import OrderEvent, FillEvent
from .base import Broker


class SimulatedBroker(Broker):
    """Backtest broker: fills at given price with commission."""

    def __init__(
        self,
        commission_rate: float = 0.00025,  # 万2.5
        min_commission: float = 5.0,       # 最低5元
        slippage: float = 0.0,             # 滑点（暂不使用）
    ) -> None:
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.slippage = slippage

    def submit_order(self, order: OrderEvent, fill_price: float) -> FillEvent:
        cost = fill_price * order.quantity
        commission = max(cost * self.commission_rate, self.min_commission)
        logger.debug(
            f"FILL {order.side.name} {order.symbol} qty={order.quantity} "
            f"price={fill_price:.2f} comm={commission:.2f}"
        )
        return FillEvent(
            order_id=order.order_id,
            symbol=order.symbol,
            dt=order.dt,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            commission=commission,
        )

    def cancel_order(self, order_id: str) -> bool:
        return True  # no-op in backtest
