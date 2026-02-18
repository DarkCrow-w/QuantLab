"""回测相关 LangChain Tools — 包装 backtest_service 现有函数。"""

from __future__ import annotations

import json
from typing import Optional

from langchain_core.tools import tool

from server.models.backtest import BacktestRequest
from server.services.backtest_service import (
    STRATEGY_REGISTRY,
    get_strategy_list,
    run_backtest,
)


@tool
def run_backtest_tool(
    symbols: list[str],
    start_date: str,
    end_date: str,
    strategy: str,
    strategy_params: Optional[dict] = None,
    initial_cash: float = 1_000_000,
    max_position_pct: float = 0.3,
    max_drawdown: float = 0.2,
    commission_rate: float = 0.00025,
) -> str:
    """执行股票回测。

    Args:
        symbols: 股票代码列表，例如 ["600519"]
        start_date: 回测开始日期，格式 YYYY-MM-DD
        end_date: 回测结束日期，格式 YYYY-MM-DD
        strategy: 策略名称，可选值: ma_cross, vol_kdj_bbi, bbi_kdj_trend
        strategy_params: 策略参数字典，例如 {"fast_period": 5, "slow_period": 20}
        initial_cash: 初始资金，默认 100 万
        max_position_pct: 单票最大仓位比例，默认 0.3
        max_drawdown: 最大回撤止损线，默认 0.2
        commission_rate: 佣金费率，默认 0.00025 (万2.5)

    Returns:
        回测结果的 JSON 字符串，包含 metrics, trades, equity_curve
    """
    req = BacktestRequest(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        strategy=strategy,
        strategy_params=strategy_params or {},
        initial_cash=initial_cash,
        max_position_pct=max_position_pct,
        max_drawdown=max_drawdown,
        commission_rate=commission_rate,
    )
    result = run_backtest(req)

    # 精简输出：完整 metrics + 交易摘要 + 权益曲线首尾
    output = {
        "metrics": result.metrics.model_dump(),
        "trade_count": len(result.trades),
        "trades_summary": [
            {
                "dt": t.dt,
                "symbol": t.symbol,
                "side": t.side,
                "qty": t.qty,
                "price": t.price,
                "commission": t.commission,
            }
            for t in result.trades[:20]  # 最多展示前 20 条
        ],
        "equity_curve_length": len(result.equity_curve),
        "equity_start": result.equity_curve[0].model_dump() if result.equity_curve else None,
        "equity_end": result.equity_curve[-1].model_dump() if result.equity_curve else None,
    }
    return json.dumps(output, ensure_ascii=False, default=str)


@tool
def list_strategies_tool() -> str:
    """列出所有可用的交易策略及其参数定义。

    Returns:
        策略列表的 JSON 字符串，每个策略包含 name, display_name, params_schema
    """
    strategies = get_strategy_list()
    output = [
        {
            "name": s.name,
            "display_name": s.display_name,
            "params_schema": [p.model_dump() for p in s.params_schema],
        }
        for s in strategies
    ]
    return json.dumps(output, ensure_ascii=False)


@tool
def compare_backtests_tool(
    backtest_configs: list[dict],
) -> str:
    """对比多组回测结果。每组配置包含 symbols, start_date, end_date, strategy, strategy_params。

    Args:
        backtest_configs: 回测配置列表，每个元素是一个字典，包含:
            - symbols: 股票代码列表
            - start_date: 开始日期
            - end_date: 结束日期
            - strategy: 策略名称
            - strategy_params: 策略参数（可选）

    Returns:
        各组回测指标对比的 JSON 字符串
    """
    results = []
    for cfg in backtest_configs:
        req = BacktestRequest(
            symbols=cfg["symbols"],
            start_date=cfg["start_date"],
            end_date=cfg["end_date"],
            strategy=cfg["strategy"],
            strategy_params=cfg.get("strategy_params", {}),
            initial_cash=cfg.get("initial_cash", 1_000_000),
            max_position_pct=cfg.get("max_position_pct", 0.3),
            max_drawdown=cfg.get("max_drawdown", 0.2),
            commission_rate=cfg.get("commission_rate", 0.00025),
        )
        try:
            result = run_backtest(req)
            results.append({
                "config": {
                    "symbols": cfg["symbols"],
                    "strategy": cfg["strategy"],
                    "strategy_params": cfg.get("strategy_params", {}),
                    "date_range": f"{cfg['start_date']} ~ {cfg['end_date']}",
                },
                "metrics": result.metrics.model_dump(),
                "status": "success",
            })
        except Exception as e:
            results.append({
                "config": cfg,
                "status": "error",
                "error": str(e),
            })

    return json.dumps(results, ensure_ascii=False, default=str)
