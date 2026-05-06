from __future__ import annotations

from pydantic import BaseModel


class ParamSchema(BaseModel):
    name: str
    type: str
    default: int | float
    min: int | float
    max: int | float
    label: str


class StrategyInfo(BaseModel):
    name: str
    display_name: str
    params_schema: list[ParamSchema]
