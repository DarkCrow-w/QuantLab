from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    symbols: list[str] = Field(default=["600519"], description="股票代码列表")
    start_date: str = Field(default="2023-01-01", description="开始日期")
    end_date: str = Field(default="2024-12-31", description="结束日期")
    strategy: str = Field(default="ma_cross", description="策略名称")
    strategy_params: dict = Field(default_factory=dict, description="策略参数")
    initial_cash: float = Field(default=1_000_000, description="初始资金")
    max_position_pct: float = Field(default=0.3, description="单票最大仓位比例")
    max_drawdown: float = Field(default=0.2, description="最大回撤熔断阈值")
    commission_rate: float = Field(default=0.00025, description="佣金费率")


class PerformanceMetrics(BaseModel):
    initial_cash: float
    final_equity: float
    total_return: float
    annual_return: float
    max_drawdown: float
    trade_count: int
    total_commission: float
    win_rate: float | None = None
    sharpe_ratio: float | None = None
    profit_loss_ratio: float | None = None


class TradeRecord(BaseModel):
    dt: str
    symbol: str
    side: str
    qty: int
    price: float
    commission: float


class EquityPoint(BaseModel):
    dt: str
    equity: float


class KlineBar(BaseModel):
    dt: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class BacktestResult(BaseModel):
    metrics: PerformanceMetrics
    equity_curve: list[EquityPoint]
    trades: list[TradeRecord]
    kline_data: dict[str, list[KlineBar]]


GridSortKey = Literal[
    "total_return",
    "annual_return",
    "max_drawdown",
    "sharpe_ratio",
    "win_rate",
    "final_equity",
]


class BacktestGridRequest(BaseModel):
    base: BacktestRequest = Field(default_factory=BacktestRequest)
    parameters: dict[str, list[Any]] = Field(
        default_factory=dict,
        description="Parameter grid, for example {'fast_period': [5, 10], 'slow_period': [20, 30]}",
    )
    max_runs: int = Field(default=30, ge=1, le=100)
    sort_by: GridSortKey = "total_return"
    sort_order: Literal["asc", "desc"] = "desc"


class BacktestGridItem(BaseModel):
    status: Literal["completed", "failed"]
    strategy_params: dict[str, Any]
    request: BacktestRequest
    metrics: PerformanceMetrics | None = None
    run_id: str | None = None
    error: str | None = None


class BacktestGridResult(BaseModel):
    requested: int
    completed: int
    failed: int
    sort_by: GridSortKey
    sort_order: Literal["asc", "desc"]
    best: BacktestGridItem | None = None
    results: list[BacktestGridItem]
