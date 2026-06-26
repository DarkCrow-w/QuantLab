#!/usr/bin/env python3
"""Command-line backtest entry for QuantLab.

Examples:

  python run_backtest.py
  python run_backtest.py -s 600519 000858
  python run_backtest.py -s 600519 --fast 10 --slow 30
  python run_backtest.py --start 2022-01-01 --end 2024-06-30
  python run_backtest.py -c configs/backtest_ma_cross.yaml
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from loguru import logger

from quant.strategy.registry import BASIC_STRATEGY_CLASSES
from server.models.backtest import BacktestRequest, BacktestResult
from server.services.backtest_service import run_backtest

STRATEGY_MAP = BASIC_STRATEGY_CLASSES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QuantLab command-line backtest")
    parser.add_argument("-c", "--config", help="YAML configuration file path")
    parser.add_argument("-s", "--symbols", nargs="+", default=["600519"], help="Stock symbols")
    parser.add_argument("--start", default="2023-01-01", help="Start date")
    parser.add_argument("--end", default="2024-12-31", help="End date")
    parser.add_argument("--strategy", default="ma_cross", choices=sorted(BASIC_STRATEGY_CLASSES), help="Strategy name")
    parser.add_argument("--fast", type=int, default=5, help="Fast MA period for ma_cross")
    parser.add_argument("--slow", type=int, default=20, help="Slow MA period for ma_cross")
    parser.add_argument("--cash", type=float, default=1_000_000, help="Initial cash")
    parser.add_argument("--pos-pct", type=float, default=0.3, help="Max position percent per symbol")
    parser.add_argument("--max-drawdown", type=float, default=0.2, help="Max drawdown circuit breaker")
    parser.add_argument("--commission-rate", type=float, default=0.00025, help="Commission rate")
    parser.add_argument("--output-dir", default="results", help="Output directory")
    return parser.parse_args()


def load_config(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as file:
        loaded = yaml.safe_load(file)
    return loaded or {}


def request_from_config(config: dict[str, Any]) -> BacktestRequest:
    data = config.get("data", {})
    strategy = config.get("strategy", {})
    risk = config.get("risk", {})
    broker = config.get("broker", {})
    engine = config.get("engine", {})
    return BacktestRequest(
        symbols=list(data.get("symbols", ["600519"])),
        start_date=str(data.get("start_date", "2023-01-01")),
        end_date=str(data.get("end_date", "2024-12-31")),
        strategy=str(strategy.get("name", "ma_cross")),
        strategy_params=dict(strategy.get("params", {})),
        initial_cash=float(engine.get("initial_cash", 1_000_000)),
        max_position_pct=float(risk.get("max_position_pct", 0.3)),
        max_drawdown=float(risk.get("max_drawdown", 0.2)),
        commission_rate=float(broker.get("commission_rate", 0.00025)),
    )


def request_from_args(args: argparse.Namespace) -> BacktestRequest:
    params: dict[str, Any] = {}
    if args.strategy == "ma_cross":
        params = {"fast_period": args.fast, "slow_period": args.slow}
    return BacktestRequest(
        symbols=args.symbols,
        start_date=args.start,
        end_date=args.end,
        strategy=args.strategy,
        strategy_params=params,
        initial_cash=args.cash,
        max_position_pct=args.pos_pct,
        max_drawdown=args.max_drawdown,
        commission_rate=args.commission_rate,
    )


def write_outputs(result: BacktestResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "metrics.json"
    trades_path = output_dir / "trades.csv"
    equity_path = output_dir / "equity_curve.csv"

    metrics_path.write_text(
        json.dumps(result.metrics.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    pd.DataFrame([item.model_dump() for item in result.equity_curve]).to_csv(equity_path, index=False)
    pd.DataFrame([item.model_dump() for item in result.trades]).to_csv(trades_path, index=False)

    logger.info("Metrics saved to {}", metrics_path)
    logger.info("Equity curve saved to {}", equity_path)
    logger.info("Trades saved to {}", trades_path)


def print_summary(result: BacktestResult) -> None:
    metrics = result.metrics
    print("")
    print("Backtest summary")
    print("----------------")
    print(f"Final equity     : {metrics.final_equity:,.2f}")
    print(f"Total return     : {metrics.total_return:.2%}")
    print(f"Annual return    : {metrics.annual_return:.2%}")
    print(f"Max drawdown     : {metrics.max_drawdown:.2%}")
    print(f"Trade count      : {metrics.trade_count}")
    print(f"Total commission : {metrics.total_commission:,.2f}")
    if metrics.sharpe_ratio is not None:
        print(f"Sharpe ratio     : {metrics.sharpe_ratio:.4f}")
    if metrics.win_rate is not None:
        print(f"Win rate         : {metrics.win_rate:.2%}")


def main() -> None:
    args = parse_args()
    request = request_from_config(load_config(args.config)) if args.config else request_from_args(args)
    result = run_backtest(request)
    print_summary(result)
    write_outputs(result, Path(args.output_dir))


if __name__ == "__main__":
    main()
