from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import uuid4

from .bar import Bar
from .order import OrderSide, OrderType


@dataclass(frozen=True, slots=True)
class MarketEvent:
    """New bar(s) available."""

    dt: date
    bars: dict[str, Bar]  # symbol -> Bar


@dataclass(frozen=True, slots=True)
class SignalEvent:
    """Strategy output: desired direction + strength."""

    symbol: str
    dt: date
    direction: OrderSide
    strength: float = 1.0  # 0..1, used by risk manager to size


@dataclass(frozen=True, slots=True)
class OrderEvent:
    """Concrete order after risk approval."""

    symbol: str
    dt: date
    side: OrderSide
    order_type: OrderType
    quantity: int  # A股以手为单位时由风控换算，这里用股数
    price: float = 0.0  # limit price; 0 = market
    order_id: str = field(default_factory=lambda: uuid4().hex[:12])


@dataclass(frozen=True, slots=True)
class FillEvent:
    """Execution report."""

    order_id: str
    symbol: str
    dt: date
    side: OrderSide
    quantity: int
    price: float
    commission: float
