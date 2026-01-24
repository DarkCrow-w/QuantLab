from __future__ import annotations

from pydantic import BaseModel, Field


class ScreenRequest(BaseModel):
    strategy: str
    strategy_params: dict = Field(default_factory=dict)
    scan_date: str | None = None
    lookback: int = 120


class ScreenMatch(BaseModel):
    symbol: str
    signal_date: str
    close: float
    volume: float
    amount: float
    strength: float


class ScreenResult(BaseModel):
    strategy: str
    scan_date: str
    total_scanned: int
    matches: list[ScreenMatch]
    elapsed_seconds: float
