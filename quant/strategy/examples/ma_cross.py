from __future__ import annotations

from quant.core.events import SignalEvent
from quant.core.order import OrderSide
from quant.strategy.base import Context, Strategy


class MACrossStrategy(Strategy):
    """Moving average crossover strategy.

    Params:
        fast_period: short MA window (default 5)
        slow_period: long MA window (default 20)
    """

    def on_bar(self, ctx: Context) -> list[SignalEvent]:
        fast_n = self.params.get("fast_period", 5)
        slow_n = self.params.get("slow_period", 20)
        signals: list[SignalEvent] = []

        for symbol, bar in ctx.bars.items():
            closes = ctx.closes(symbol)
            if len(closes) < slow_n + 1:
                continue

            fast_ma = sum(closes[-fast_n:]) / fast_n
            slow_ma = sum(closes[-slow_n:]) / slow_n
            prev_fast = sum(closes[-fast_n - 1:-1]) / fast_n
            prev_slow = sum(closes[-slow_n - 1:-1]) / slow_n

            # Golden cross: fast crosses above slow
            if prev_fast <= prev_slow and fast_ma > slow_ma:
                signals.append(SignalEvent(
                    symbol=symbol, dt=bar.dt,
                    direction=OrderSide.BUY, strength=1.0,
                ))
            # Death cross: fast crosses below slow
            elif prev_fast >= prev_slow and fast_ma < slow_ma:
                pos = ctx.portfolio_snapshot.get("positions", {})
                if symbol in pos and pos[symbol]["qty"] > 0:
                    signals.append(SignalEvent(
                        symbol=symbol, dt=bar.dt,
                        direction=OrderSide.SELL, strength=1.0,
                    ))

        return signals
