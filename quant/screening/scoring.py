"""多因子评分引擎（多因子选股核心）。

把五维因子分（trend/momentum/volume/dip/risk）按可配置权重加权成综合分，
再用 trading_plus 移植的高级形态（三波 / 麒麟会 / 沙漏）做乘性/加性调整，
最后映射到 ★ 评级。硬过滤（蜈蚣图 / 沙漏分 / 成交额 / 价格）只置位 ``passed_filter``，
**不在此处丢弃**（由服务层决定），分数照常计算。

设计原则：
- 入参 ``df`` 为升序（按 ``dt``）DataFrame，含 OHLCV 与 20 指标全列。
- 数据不足时各因子返回中性/安全默认值，引擎不抛异常。
- ``signal_date = str(df.iloc[-1].dt)``；``pct_chg`` 用 ``close.pct_change()*100`` 的最后值。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .factors import (
    FACTOR_DEFS,
    score_dip,
    score_momentum,
    score_risk,
    score_trend,
    score_volume,
)
from .patterns import centipede, kirin_stage, sandglass_score, three_waves

# 因子 key → 默认权重映射（来自 FACTOR_DEFS）
_DEFAULT_WEIGHTS: dict[str, float] = {
    d["key"]: float(d["default_weight"]) for d in FACTOR_DEFS
}

# 评级阈值（分数下界从高到低）
RATING_TIERS: list[tuple[float, str]] = [
    (80, "★★★★★ 强烈推荐"),
    (65, "★★★★☆ 推荐"),
    (50, "★★★☆☆ 可关注"),
    (35, "★★☆☆☆ 谨慎"),
    (0, "★☆☆☆☆ 不推荐"),
]


@dataclass
class ScoreConfig:
    """评分配置。

    weights:           覆盖 FACTOR_DEFS 默认权重；缺失键用默认；评分时自动归一化。
    exclude_centipede: 蜈蚣图硬过滤（命中则 passed_filter=False）。
    min_sandglass:     沙漏分硬过滤下限（trading_plus 习惯用 50）。
    min_amount:        最小成交额（元）过滤低流动性。
    min_price:         最低价过滤。
    use_patterns:      是否计算 three_waves/kirin/sandglass 并做加权调整。
    """

    weights: dict[str, float] = field(default_factory=lambda: dict(_DEFAULT_WEIGHTS))
    exclude_centipede: bool = True
    min_sandglass: float = 0.0
    min_amount: float = 0.0
    min_price: float = 0.0
    use_patterns: bool = True


@dataclass
class StockScore:
    """单只股票的多因子评分结果。"""

    symbol: str
    score: float
    rating: str
    factors: dict[str, float]
    reasons: list[str]
    warnings: list[str]
    # 快照
    signal_date: str
    close: float
    pct_chg: float
    volume: float
    amount: float
    # 形态标签（use_patterns 时填充）
    sandglass: float
    wave: str
    kirin: str
    passed_filter: bool


# ──────────────────────────────────────────────────────────────────────────
# 内部工具
# ──────────────────────────────────────────────────────────────────────────
def _f(value: object, default: float = 0.0) -> float:
    """安全转 float：None/NaN/Inf/异常 → default。"""
    try:
        if value is None:
            return default
        out = float(value)  # type: ignore[arg-type]
        if math.isnan(out) or math.isinf(out):
            return default
        return out
    except (TypeError, ValueError):
        return default


def _normalize_weights(weights: dict[str, float] | None) -> dict[str, float]:
    """合并默认权重后归一化（和为 1）。

    - 缺失键用默认权重补齐；未知键忽略；负值截 0。
    - 全为 0 时回退到默认权重的归一化。
    """
    merged = dict(_DEFAULT_WEIGHTS)
    if weights:
        for k, v in weights.items():
            if k in _DEFAULT_WEIGHTS:
                merged[k] = max(0.0, _f(v, 0.0))
    total = sum(merged.values())
    if total <= 0:
        # 退回默认权重
        merged = dict(_DEFAULT_WEIGHTS)
        total = sum(merged.values())
    return {k: v / total for k, v in merged.items()}


def _last_pct_chg(df: pd.DataFrame) -> float:
    """最后一日涨跌幅 (%) = close.pct_change().iloc[-1]*100。数据不足返回 0。"""
    if df is None or "close" not in df.columns or len(df) < 2:
        return 0.0
    close = pd.to_numeric(df["close"], errors="coerce")
    chg = close.pct_change().iloc[-1]
    return round(_f(chg, 0.0) * 100.0, 2)


def rating_for(score: float) -> str:
    """分数映射到 ★ 评级（取首个满足 score>=阈值 的档位）。"""
    s = _f(score, 0.0)
    for threshold, label in RATING_TIERS:
        if s >= threshold:
            return label
    return RATING_TIERS[-1][1]


def default_config() -> ScoreConfig:
    """返回一份默认评分配置。"""
    return ScoreConfig()


# ──────────────────────────────────────────────────────────────────────────
# 评分引擎
# ──────────────────────────────────────────────────────────────────────────
class MultiFactorScorer:
    """多因子评分引擎：五因子加权 + 形态调整 + 评级 + 硬过滤标记。"""

    def __init__(self, config: ScoreConfig | None = None) -> None:
        self.config = config if config is not None else default_config()
        self._norm_weights = _normalize_weights(self.config.weights)

    def score(self, symbol: str, df: pd.DataFrame) -> StockScore:
        """计算五因子 → 加权综合 → 形态调整 → 评级 → 硬过滤标记。

        综合 = Σ(归一化权重 * 因子分)。
        形态调整（use_patterns）：建仓波 ×1.05；冲刺波 或 麒麟派发 ×0.7；
        麒麟吸筹 ×1.08；沙漏 is_perfect +10。最终 clip 0-100。
        硬过滤：exclude_centipede 命中 / sandglass<min_sandglass /
        amount<min_amount / close<min_price → passed_filter=False（分数照算）。
        """
        cfg = self.config

        # ===== 五维因子 =====
        f_trend, r_trend = score_trend(df)
        f_mom, r_mom = score_momentum(df)
        f_vol, r_vol = score_volume(df)
        f_dip, r_dip = score_dip(df)
        f_risk, w_risk = score_risk(df)

        factors: dict[str, float] = {
            "trend": round(_f(f_trend, 50.0), 1),
            "momentum": round(_f(f_mom, 50.0), 1),
            "volume": round(_f(f_vol, 50.0), 1),
            "dip": round(_f(f_dip, 50.0), 1),
            "risk": round(_f(f_risk, 60.0), 1),
        }

        # ===== 加权综合 =====
        composite = sum(self._norm_weights[k] * factors[k] for k in self._norm_weights)

        reasons: list[str] = []
        warnings: list[str] = []
        # 因子利好理由（trend/momentum/volume/dip）
        for rs in (r_trend, r_mom, r_vol, r_dip):
            for r in rs:
                if r and r != "数据不足" and r not in reasons:
                    reasons.append(r)
        # 风险因子的 warnings
        for w in w_risk:
            if w and w not in ("无明显风险", "数据不足") and w not in warnings:
                warnings.append(w)

        # ===== 快照 =====
        last = df.iloc[-1] if df is not None and len(df) > 0 else None
        signal_date = str(last["dt"]) if last is not None and "dt" in df.columns else ""
        close = _f(last["close"], 0.0) if last is not None and "close" in df.columns else 0.0
        volume = _f(last["volume"], 0.0) if last is not None and "volume" in df.columns else 0.0
        amount = _f(last["amount"], 0.0) if last is not None and "amount" in df.columns else 0.0
        pct_chg = _last_pct_chg(df)

        # ===== 形态计算 + 调整 =====
        sandglass_val = 0.0
        wave_label = "未知"
        kirin_label = "未知"

        if cfg.use_patterns:
            sg = sandglass_score(df)
            wave = three_waves(df)
            kirin = kirin_stage(df)

            sandglass_val = float(sg.get("score", 0))
            wave_label = str(wave.get("wave", "未知"))
            kirin_label = str(kirin.get("stage", "未知"))

            # 建仓波 ×1.05（利好）
            if wave_label == "建仓波":
                composite *= 1.05
                reasons.append("三波-建仓波(可干)")
            # 麒麟吸筹 ×1.08（利好）
            if kirin_label == "吸筹":
                composite *= 1.08
                reasons.append("麒麟会-吸筹阶段")
            # 冲刺波 或 麒麟派发 ×0.7（风险）——按 spec 为"或"，只惩罚一次，避免双重叠加
            if wave_label == "冲刺波" or kirin_label == "派发":
                composite *= 0.7
                if wave_label == "冲刺波":
                    warnings.append("三波-冲刺波(高位风险)")
                if kirin_label == "派发":
                    warnings.append("麒麟会-派发阶段")
            # 沙漏 is_perfect +10（利好）
            if sg.get("is_perfect"):
                composite += 10.0
                reasons.append(f"沙漏极佳({int(sandglass_val)}分)")
        score_val = round(max(0.0, min(100.0, composite)), 1)
        rating = rating_for(score_val)

        # ===== 硬过滤标记 =====
        passed = True
        if cfg.use_patterns and cfg.exclude_centipede:
            cp = centipede(df)
            if cp.get("is_centipede"):
                passed = False
                warnings.append("蜈蚣图(无序震荡，已过滤)")
        if cfg.use_patterns and sandglass_val < cfg.min_sandglass:
            passed = False
        if amount < cfg.min_amount:
            passed = False
        if close < cfg.min_price:
            passed = False

        if not reasons:
            reasons.append("无明显利好")
        if not warnings:
            warnings.append("无明显风险")

        return StockScore(
            symbol=symbol,
            score=score_val,
            rating=rating,
            factors=factors,
            reasons=reasons,
            warnings=warnings,
            signal_date=signal_date,
            close=round(close, 3),
            pct_chg=pct_chg,
            volume=volume,
            amount=amount,
            sandglass=round(sandglass_val, 1),
            wave=wave_label,
            kirin=kirin_label,
            passed_filter=passed,
        )


__all__ = [
    "ScoreConfig",
    "StockScore",
    "RATING_TIERS",
    "MultiFactorScorer",
    "rating_for",
    "default_config",
]
