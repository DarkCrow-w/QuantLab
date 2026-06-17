from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ManagedFactorDraft(BaseModel):
    key: str = Field(min_length=2, max_length=60)
    label: str = Field(min_length=1, max_length=80)
    category: str = "custom"
    description: str = ""
    expression: str = ""
    default_weight: float = Field(1, ge=0, le=100)
    enabled: bool = True


class ManagedFactor(ManagedFactorDraft):
    id: str
    source: Literal["builtin", "custom"] = "custom"
    created_at: str
    updated_at: str


class FactorMiningRequest(BaseModel):
    symbols: list[str] | None = None
    lookback: int = Field(180, ge=60, le=1000)
    forward_days: int = Field(5, ge=1, le=60)
    min_samples: int = Field(20, ge=5, le=500)


class FactorMiningItem(BaseModel):
    key: str
    label: str
    category: str
    samples: int
    ic: float | None
    abs_ic: float | None
    coverage: float
    direction: str


class FactorMiningResult(BaseModel):
    symbols: int
    lookback: int
    forward_days: int
    items: list[FactorMiningItem]
    warnings: list[str] = []
