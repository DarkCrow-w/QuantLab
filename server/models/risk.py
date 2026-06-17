from __future__ import annotations

from pydantic import BaseModel, Field


class RiskRuleDraft(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = ""
    max_position_pct: float = Field(0.3, gt=0, le=1)
    max_drawdown: float = Field(0.2, gt=0, le=1)
    max_single_order_pct: float = Field(0.1, gt=0, le=1)
    stop_loss_pct: float = Field(0.08, gt=0, le=1)
    take_profit_pct: float = Field(0.25, gt=0, le=5)
    max_symbols: int = Field(10, ge=1, le=500)
    enabled: bool = True


class RiskRule(RiskRuleDraft):
    id: str
    created_at: str
    updated_at: str


class RiskEvaluationRequest(BaseModel):
    rule_id: str | None = None
    draft: RiskRuleDraft | None = None
    equity: float = Field(100000, gt=0)
    position_value: float = Field(0, ge=0)
    order_value: float = Field(0, ge=0)
    drawdown: float = Field(0, ge=0)
    symbol_count: int = Field(0, ge=0)


class RiskEvaluationCheck(BaseModel):
    key: str
    label: str
    passed: bool
    message: str
    severity: str = "error"


class RiskEvaluationResult(BaseModel):
    passed: bool
    rule: RiskRuleDraft
    checks: list[RiskEvaluationCheck]
