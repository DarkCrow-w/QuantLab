#!/usr/bin/env python3
"""Live trading entry point.

Usage:

  python run_live.py configs/live_ma_cross.yaml
"""

from __future__ import annotations

import argparse

import yaml

from quant.config import get_settings
from quant.data.akshare_feed import AKShareFeed
from quant.engine.live import LiveEngine
from quant.execution.futu import FutuBroker
from quant.risk.basic import BasicRiskManager
from quant.strategy.registry import BASIC_STRATEGY_CLASSES, get_basic_strategy_class

STRATEGY_MAP = BASIC_STRATEGY_CLASSES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QuantLab live trading entry")
    parser.add_argument(
        "config",
        nargs="?",
        help="YAML configuration file path, for example configs/live_ma_cross.yaml",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.config:
        raise SystemExit("Usage: python run_live.py <config.yaml>")

    with open(args.config, encoding="utf-8") as file:
        cfg = yaml.safe_load(file)

    feed = AKShareFeed(
        start_date=cfg["data"]["start_date"],
        end_date=cfg["data"]["end_date"],
        use_cache=cfg["data"].get("use_cache", False),
    )
    feed.subscribe(cfg["data"]["symbols"])

    strategy_name = cfg["strategy"]["name"]
    strategy = get_basic_strategy_class(strategy_name)(params=cfg["strategy"].get("params", {}))

    risk_cfg = cfg.get("risk", {})
    risk_manager = BasicRiskManager(
        max_position_pct=risk_cfg.get("max_position_pct", 0.3),
        max_drawdown=risk_cfg.get("max_drawdown", 0.2),
    )

    broker_cfg = cfg.get("broker", {})
    futu_settings = get_settings().futu
    broker = FutuBroker(
        host=broker_cfg.get("host", futu_settings.host),
        port=broker_cfg.get("port", futu_settings.port),
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
