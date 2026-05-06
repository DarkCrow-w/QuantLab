from __future__ import annotations

from loguru import logger

from quant.core.portfolio import Portfolio
from quant.data.base import DataFeed
from quant.execution.base import Broker
from quant.risk.base import RiskManager
from quant.strategy.base import Context, Strategy


class LiveEngine:
    """Live trading engine with APScheduler."""

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

    def tick(self) -> None:
        """Execute one trading cycle — called by scheduler."""
        event = self.feed.update()
        if event is None:
            logger.warning("No market data available")
            return

        prices = {sym: bar.close for sym, bar in event.bars.items()}
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

        for sig in signals:
            price = prices.get(sig.symbol)
            if price is None:
                continue
            order = self.risk.approve(sig, self.portfolio, price)
            if order is None:
                continue
            fill = self.broker.submit_order(order, price)
            self.portfolio.update_on_fill(fill)
            logger.info(
                f"LIVE FILL: {fill.side.name} {fill.symbol} "
                f"qty={fill.quantity} price={fill.price:.2f}"
            )

    def run(self, cron_hour: int = 15, cron_minute: int = 5) -> None:
        """Start scheduler — runs tick() at specified time on weekdays."""
        from apscheduler.schedulers.blocking import BlockingScheduler
        scheduler = BlockingScheduler()
        scheduler.add_job(
            self.tick,
            "cron",
            day_of_week="mon-fri",
            hour=cron_hour,
            minute=cron_minute,
        )
        logger.info(f"Live engine scheduled at {cron_hour:02d}:{cron_minute:02d} weekdays")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Live engine stopped")
