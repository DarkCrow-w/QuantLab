from __future__ import annotations

from pydantic import BaseModel, Field


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


class StrategyAssetDraft(BaseModel):
    name: str
    description: str = ""
    base_strategy: str
    params: dict[str, int | float] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True


class StrategyAsset(StrategyAssetDraft):
    id: str
    created_at: str
    updated_at: str
