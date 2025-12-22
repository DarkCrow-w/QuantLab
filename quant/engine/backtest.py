from __future__ import annotations

from datetime import date

import pandas as pd
from loguru import logger

from quant.core.events import FillEvent
from quant.core.portfolio import Portfolio
from quant.data.base import DataFeed
from quant.execution.base import Broker
from quant.risk.base import RiskManager
from quant.strategy.base import Context, Strategy


class BacktestEngine:
    """Event-driven backtest engine."""

    def __init__(
        self,
        feed: DataFeed,
        strategy: Strategy,
        risk_manager: RiskManager,
        broker: Broker,
        initial_cash: float = 1_000_000.0,
    ) -> None:
        self.feed = feed
        self.strategy = strategy
        self.risk = risk_manager
        self.broker = broker
        self.portfolio = Portfolio(initial_cash=initial_cash)
        self.equity_curve: list[dict] = []
        self.trades: list[dict] = []

    def _current_prices(self, bars: dict) -> dict[str, float]:
        return {sym: bar.close for sym, bar in bars.items()}

    def run(self) -> pd.DataFrame:
        logger.info("Backtest started")
        bar_count = 0
        pending_orders = []  # orders waiting for next bar fill

        while self.feed.has_more():
            event = self.feed.update()
            if event is None:
                break

            # 1. Fill pending orders at this bar's open price
            for order in pending_orders:
                sym = order.symbol
                if sym not in event.bars:
                    continue
                fill_price = event.bars[sym].open  # next-bar open
                fill = self.broker.submit_order(order, fill_price)
                self.portfolio.update_on_fill(fill)
                self.trades.append({
                    "dt": fill.dt,
                    "symbol": fill.symbol,
                    "side": fill.side.name,
                    "qty": fill.quantity,
                    "price": fill.price,
                    "commission": fill.commission,
                })
            pending_orders.clear()

            # 2. Build context and run strategy
            prices = self._current_prices(event.bars)
            history = {
                sym: self.feed.get_latest_bars(sym, n=9999)
                for sym in event.bars
            }
            ctx = Context(
                bars=event.bars,
                history=history,
                portfolio_snapshot=self.portfolio.snapshot(prices),
                current_date=event.dt,
            )
            signals = self.strategy.on_bar(ctx)

            # 3. Risk check and generate orders
            for sig in signals:
                price = prices.get(sig.symbol)
                if price is None:
                    continue
                order = self.risk.approve(sig, self.portfolio, price)
                if order is not None:
                    pending_orders.append(order)

            # 4. Record equity
            equity = self.portfolio.equity(prices)
            self.equity_curve.append({"dt": event.dt, "equity": equity})
            bar_count += 1

        logger.info(f"Backtest finished: {bar_count} bars, {len(self.trades)} trades")
        return self._build_results()

    def _build_results(self) -> pd.DataFrame:
        eq = pd.DataFrame(self.equity_curve)
        if not eq.empty:
            eq["dt"] = pd.to_datetime(eq["dt"])
            eq = eq.set_index("dt")
        return eq

    def get_trades(self) -> pd.DataFrame:
        return pd.DataFrame(self.trades)

    def print_summary(self, eq: pd.DataFrame) -> None:
        if eq.empty:
            logger.warning("No equity data")
            return
        initial = self.portfolio.initial_cash
        final = eq["equity"].iloc[-1]
        ret = (final - initial) / initial
        peak = eq["equity"].cummax()
        dd = (eq["equity"] - peak) / peak
        max_dd = dd.min()
        days = (eq.index[-1] - eq.index[0]).days
        ann_ret = (1 + ret) ** (365 / max(days, 1)) - 1 if days > 0 else 0

        logger.info(f"Initial: {initial:,.0f}")
        logger.info(f"Final:   {final:,.0f}")
        logger.info(f"Return:  {ret:.2%}")
        logger.info(f"Annual:  {ann_ret:.2%}")
        logger.info(f"MaxDD:   {max_dd:.2%}")
        logger.info(f"Trades:  {len(self.trades)}")
        logger.info(f"Commission: {self.portfolio.total_commission:,.2f}")

    def generate_report(self, output_path: str = "results/report.html") -> None:
        """Generate quantstats HTML report."""
        import quantstats as qs
        eq = pd.DataFrame(self.equity_curve)
        if eq.empty:
            return
        eq["dt"] = pd.to_datetime(eq["dt"])
        eq = eq.set_index("dt")
        returns = eq["equity"].pct_change().dropna()
        returns.index = pd.to_datetime(returns.index)
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        qs.reports.html(returns, output=output_path, title="Backtest Report")
        logger.info(f"Report saved to {output_path}")
