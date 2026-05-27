"""多因子选股引擎包。

子模块：
- patterns: 移植 trading_plus 高级形态（向量化 / 快照）
- factors:  五维因子打分
- scoring:  多因子评分引擎
"""

from __future__ import annotations

from .patterns import (
    slope,
    sandglass_score,
    centipede,
    three_waves,
    kirin_stage,
)
from .factors import (
    score_trend,
    score_momentum,
    score_volume,
    score_dip,
    score_risk,
    FACTOR_DEFS,
)
from .scoring import (
    ScoreConfig,
    StockScore,
    RATING_TIERS,
    MultiFactorScorer,
    rating_for,
    default_config,
)

__all__ = [
    # patterns
    "slope",
    "sandglass_score",
    "centipede",
    "three_waves",
    "kirin_stage",
    # factors
    "score_trend",
    "score_momentum",
    "score_volume",
    "score_dip",
    "score_risk",
    "FACTOR_DEFS",
    # scoring
    "ScoreConfig",
    "StockScore",
    "RATING_TIERS",
    "MultiFactorScorer",
    "rating_for",
    "default_config",
]
