from __future__ import annotations

import pandas as pd

from quant.core.events import SignalEvent
from quant.core.order import OrderSide
from quant.data import indicators
from quant.screening.composer import Condition, MetricContext, evaluate_condition
from quant.strategy.base import Context, Strategy
from server.models.screening import FactorStrategyDraft


class CompositeRuleStrategy(Strategy):
    """Backtest adapter for visual condition-composer strategies.

    A symbol is bought when enabled strategy groups pass and the weighted score
    reaches ``min_score``. A held symbol is sold once the rule no longer passes.
    """

    def __init__(self, definition: FactorStrategyDraft, params: dict | None = None) -> None:
        super().__init__(params)
        self.definition = definition

    def on_bar(self, ctx: Context) -> list[SignalEvent]:
        signals: list[SignalEvent] = []
        positions = ctx.portfolio_snapshot.get("positions", {})
        min_bars = max(30, min(self.definition.lookback, 250))

        for symbol, bar in ctx.bars.items():
            history = ctx.history.get(symbol, [])
            if len(history) < min_bars:
                continue
            passed = self._passes(history[-self.definition.lookback :])
            has_position = symbol in positions and positions[symbol].get("qty", 0) > 0
            if passed and not has_position:
                signals.append(SignalEvent(symbol=symbol, dt=bar.dt, direction=OrderSide.BUY, strength=1.0))
            elif not passed and has_position:
                signals.append(SignalEvent(symbol=symbol, dt=bar.dt, direction=OrderSide.SELL, strength=1.0))
        return signals

    def _passes(self, history) -> bool:
        frame = pd.DataFrame(
            [
                {
                    "dt": bar.dt,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                    "amount": getattr(bar, "amount", 0.0),
                }
                for bar in history
            ]
        )
        frame = indicators.compute_all(frame)
        context = MetricContext(frame)
        group_passes: list[bool] = []
        weighted_total = 0.0
        weighted_passed = 0.0

        for group in self.definition.groups:
            required_results: list[bool] = []
            for raw in group.conditions:
                if not raw.enabled:
                    continue
                result = evaluate_condition(context, Condition(**raw.model_dump(exclude={"id"})))
                weight = max(0.0, raw.weight)
                if result.available:
                    weighted_total += weight
                    if result.passed:
                        weighted_passed += weight
                if raw.required:
                    required_results.append(result.available and result.passed)
            if not required_results:
                group_passes.append(True)
            elif group.logic == "all":
                group_passes.append(all(required_results))
            else:
                group_passes.append(any(required_results))

        hard_pass = all(group_passes) if self.definition.logic == "all" else any(group_passes)
        score = weighted_passed / weighted_total * 100 if weighted_total else 100.0
        return hard_pass and score >= self.definition.min_score
