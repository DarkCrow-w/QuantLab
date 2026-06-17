from __future__ import annotations

import pytest

from server.models.backtest import BacktestGridRequest, BacktestRequest, BacktestResult, PerformanceMetrics
from server.services.backtest_service import run_backtest_grid


def _result(total_return: float) -> BacktestResult:
    return BacktestResult(
        metrics=PerformanceMetrics(
            initial_cash=1_000_000,
            final_equity=1_000_000 * (1 + total_return),
            total_return=total_return,
            annual_return=total_return,
            max_drawdown=-0.05,
            trade_count=2,
            total_commission=10,
            win_rate=0.5,
            sharpe_ratio=total_return * 10,
        ),
        equity_curve=[],
        trades=[],
        kline_data={},
    )


def test_backtest_grid_expands_sorts_and_persists_successful_runs():
    saved: list[BacktestRequest] = []

    def runner(req: BacktestRequest) -> BacktestResult:
        fast = int(req.strategy_params["fast_period"])
        slow = int(req.strategy_params["slow_period"])
        return _result((fast * 10 + slow) / 10_000)

    def save_result(req: BacktestRequest, result: BacktestResult) -> str:
        saved.append(req)
        return f"run-{len(saved)}"

    result = run_backtest_grid(
        BacktestGridRequest(
            base=BacktestRequest(
                symbols=["600519"],
                start_date="2024-01-01",
                end_date="2024-03-31",
                strategy="ma_cross",
                strategy_params={"slow_period": 20},
            ),
            parameters={"fast_period": [5, 10], "slow_period": [20, 30]},
            sort_by="total_return",
            sort_order="desc",
            max_runs=4,
        ),
        runner=runner,
        save_result=save_result,
    )

    assert result.requested == 4
    assert result.completed == 4
    assert result.failed == 0
    assert len(saved) == 4
    assert result.best is not None
    assert result.best.strategy_params == {"slow_period": 30, "fast_period": 10}
    assert result.best.run_id == "run-4"
    returns = [item.metrics.total_return for item in result.results if item.metrics]
    assert returns == sorted(returns, reverse=True)


def test_backtest_grid_keeps_failed_combinations_at_the_end():
    def runner(req: BacktestRequest) -> BacktestResult:
        if req.strategy_params["fast_period"] == 10:
            raise RuntimeError("bad parameter")
        return _result(0.03)

    result = run_backtest_grid(
        BacktestGridRequest(
            base=BacktestRequest(strategy_params={}),
            parameters={"fast_period": [5, 10]},
            sort_by="total_return",
            sort_order="asc",
        ),
        runner=runner,
    )

    assert result.requested == 2
    assert result.completed == 1
    assert result.failed == 1
    assert result.results[0].status == "completed"
    assert result.results[1].status == "failed"
    assert result.results[1].error == "bad parameter"


def test_backtest_grid_rejects_too_many_combinations():
    req = BacktestGridRequest(
        base=BacktestRequest(),
        parameters={"a": [1, 2, 3], "b": [1, 2, 3]},
        max_runs=8,
    )

    with pytest.raises(ValueError, match="exceeding max_runs"):
        run_backtest_grid(req, runner=lambda _: _result(0.01))
