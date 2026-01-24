from __future__ import annotations

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    symbols: list[str] = Field(default=["600519"], description="股票代码列表")
    start_date: str = Field(default="2023-01-01", description="开始日期")
    end_date: str = Field(default="2024-12-31", description="结束日期")
    strategy: str = Field(default="ma_cross", description="策略名称")
    strategy_params: dict = Field(default_factory=dict, description="策略参数")
    initial_cash: float = Field(default=1_000_000, description="初始资金")
    max_position_pct: float = Field(default=0.3, description="单票最大仓位比例")
    max_drawdown: float = Field(default=0.2, description="最大回撤止损")
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
