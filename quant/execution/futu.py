from __future__ import annotations

from loguru import logger

from quant.config import get_settings
from quant.core.events import OrderEvent, FillEvent
from quant.core.order import OrderSide
from .base import Broker


class FutuBroker(Broker):
    """Live broker via Futu OpenAPI."""

    def __init__(self, host: str | None = None, port: int | None = None) -> None:
        settings = get_settings().futu
        self.host = host or settings.host
        self.port = port or settings.port
        self._ctx = None

    def _connect(self):
        if self._ctx is not None:
            return
        from futu import OpenSecTradeContext, TrdMarket
        self._ctx = OpenSecTradeContext(
            host=self.host, port=self.port, security_firm=None,
            filter_trdmarket=TrdMarket.HK,
        )
        logger.info(f"Connected to Futu at {self.host}:{self.port}")

    def submit_order(self, order: OrderEvent, fill_price: float) -> FillEvent:
        self._connect()
        from futu import TrdSide, OrderType as FutuOrderType
        side = TrdSide.BUY if order.side == OrderSide.BUY else TrdSide.SELL
        code = f"SH.{order.symbol}" if order.symbol.startswith("6") else f"SZ.{order.symbol}"

        ret, data = self._ctx.place_order(
            price=fill_price,
            qty=order.quantity,
            code=code,
            trd_side=side,
            order_type=FutuOrderType.NORMAL,
        )
        if ret != 0:
            raise RuntimeError(f"Futu place_order failed: {data}")

        order_id = str(data["order_id"].iloc[0])
        logger.info(f"Futu order placed: {order_id} {order.side.name} {code} qty={order.quantity}")

        # For simplicity, assume immediate fill
        commission = max(fill_price * order.quantity * 0.00025, 5.0)
        return FillEvent(
            order_id=order_id,
            symbol=order.symbol,
            dt=order.dt,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            commission=commission,
        )

    def cancel_order(self, order_id: str) -> bool:
        self._connect()
        ret, data = self._ctx.modify_order(
            modify_order_op=8,  # CANCEL
            order_id=order_id, qty=0, price=0,
        )
        return ret == 0
