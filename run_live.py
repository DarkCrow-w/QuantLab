#!/usr/bin/env python3
"""Live trading entry point. Usage: python run_live.py configs/live.yaml"""
from __future__ import annotations

import sys

import yaml
from loguru import logger

from quant.data.akshare_feed import AKShareFeed
from quant.engine.live import LiveEngine
from quant.execution.futu import FutuBroker
from quant.risk.basic import BasicRiskManager
from quant.strategy.examples.ma_cross import MACrossStrategy

STRATEGY_MAP = {
    "ma_cross": MACrossStrategy,
}


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python run_live.py <config.yaml>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        cfg = yaml.safe_load(f)

    # Feed — live mode fetches recent data each tick
    feed = AKShareFeed(
        start_date=cfg["data"]["start_date"],
        end_date=cfg["data"]["end_date"],
        use_cache=cfg["data"].get("use_cache", False),
    )
    feed.subscribe(cfg["data"]["symbols"])

    strat_name = cfg["strategy"]["name"]
    strategy = STRATEGY_MAP[strat_name](params=cfg["strategy"].get("params", {}))

    risk_cfg = cfg.get("risk", {})
    risk_manager = BasicRiskManager(
        max_position_pct=risk_cfg.get("max_position_pct", 0.3),
        max_drawdown=risk_cfg.get("max_drawdown", 0.2),
    )

    broker_cfg = cfg.get("broker", {})
    broker = FutuBroker(
        host=broker_cfg.get("host", "127.0.0.1"),
        port=broker_cfg.get("port", 11111),
    )

    engine = LiveEngine(
        feed=feed,
        strategy=strategy,
        risk_manager=risk_manager,
        broker=broker,
        initial_cash=cfg.get("engine", {}).get("initial_cash", 1_000_000),
    )

    schedule = cfg.get("schedule", {})
    engine.run(
        cron_hour=schedule.get("hour", 15),
        cron_minute=schedule.get("minute", 5),
    )


if __name__ == "__main__":
    main()
