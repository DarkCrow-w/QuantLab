from __future__ import annotations

from server.models.backtest import (
    BacktestRequest,
    BacktestResult,
    EquityPoint,
    KlineBar,
    PerformanceMetrics,
    TradeRecord,
)
from server.services.research_service import ResearchStore


def _sample_result() -> BacktestResult:
    return BacktestResult(
        metrics=PerformanceMetrics(
            initial_cash=1_000_000,
            final_equity=1_120_000,
            total_return=0.12,
            annual_return=0.18,
            max_drawdown=-0.04,
            trade_count=2,
            total_commission=12.5,
            win_rate=0.5,
            sharpe_ratio=1.25,
            profit_loss_ratio=1.8,
        ),
        equity_curve=[
            EquityPoint(dt="2024-01-01", equity=1_000_000),
            EquityPoint(dt="2024-01-02", equity=1_120_000),
        ],
        trades=[
            TradeRecord(
                dt="2024-01-02",
                symbol="600519",
                side="BUY",
                qty=100,
                price=100,
                commission=5,
            )
        ],
        kline_data={
            "600519": [
                KlineBar(
                    dt="2024-01-02",
                    open=100,
                    high=105,
                    low=99,
                    close=104,
                    volume=10000,
                )
            ]
        },
    )


def test_research_store_saves_and_lists_backtest_runs(tmp_path):
    store = ResearchStore(tmp_path / "research.sqlite3")
    request = BacktestRequest(
        symbols=["600519"],
        start_date="2024-01-01",
        end_date="2024-02-01",
        strategy="ma_cross",
        strategy_params={"fast_period": 5, "slow_period": 20},
    )

    saved = store.save_backtest(request, _sample_result())
    runs = store.list_backtests()
    detail = store.get_backtest(saved["id"])
    summary = store.summary()

    assert len(runs) == 1
    assert runs[0]["strategy"] == "ma_cross"
    assert runs[0]["symbols"] == ["600519"]
    assert detail is not None
    assert detail["request"]["strategy_params"]["fast_period"] == 5
    assert detail["metrics"]["total_return"] == 0.12
    assert detail["result"]["trades"][0]["side"] == "BUY"
    assert detail["tags"] == []
    assert detail["note"] == ""
    assert detail["favorite"] is False
    assert summary["total_backtests"] == 1
    assert summary["best_run"]["id"] == saved["id"]


def test_research_store_updates_and_filters_backtest_metadata(tmp_path):
    store = ResearchStore(tmp_path / "research.sqlite3")
    request = BacktestRequest(
        symbols=["600519"],
        start_date="2024-01-01",
        end_date="2024-02-01",
        strategy="ma_cross",
        strategy_params={"fast_period": 5, "slow_period": 20},
    )
    saved = store.save_backtest(request, _sample_result())

    updated = store.update_backtest_metadata(
        saved["id"],
        tags=["candidate", "grid", "candidate", ""],
        note=" Watch this parameter set ",
        favorite=True,
    )
    favorite_runs = store.list_backtests(favorite=True)
    tagged_runs = store.list_backtests(tag="grid")
    summary = store.summary()

    assert updated is not None
    assert updated["favorite"] is True
    assert updated["tags"] == ["candidate", "grid"]
    assert updated["note"] == "Watch this parameter set"
    assert favorite_runs[0]["id"] == saved["id"]
    assert tagged_runs[0]["id"] == saved["id"]
    assert summary["favorite_count"] == 1
    assert {"tag": "candidate", "count": 1} in summary["tags"]


def test_research_store_builds_markdown_report(tmp_path):
    store = ResearchStore(tmp_path / "research.sqlite3")
    request = BacktestRequest(
        symbols=["600519"],
        start_date="2024-01-01",
        end_date="2024-02-01",
        strategy="ma_cross",
        strategy_params={"fast_period": 5, "slow_period": 20},
    )
    saved = store.save_backtest(request, _sample_result())
    store.update_backtest_metadata(
        saved["id"],
        tags=["candidate"],
        note="Good baseline",
        favorite=True,
    )

    report = store.build_backtest_report([saved["id"]])

    assert report is not None
    assert "# QuantLab Research Report" in report
    assert saved["id"][:8] in report
    assert "Good baseline" in report
    assert '"fast_period": 5' in report
    assert store.build_backtest_report(["missing"]) is None
