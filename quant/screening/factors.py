"""五维因子打分模块（多因子选股引擎）。

每个评分函数接收一只股票的日线 DataFrame（升序，含已预计算的全部 20 指标列），
返回 ``(score, reasons)``：``score`` 为 0-100 的浮点分，``reasons`` 为中文短语列表
（趋势/动量/量价/抄底为利好理由，风险为扣分警示）。

设计原则（对齐 trading_plus/modules/screener.py 的评分精神，但作用于 quant 预计算列）：
- 以「最后一根 bar」（``df.iloc[-1]``，即选股截止日）做快照判断，必要时回看窗口。
- numpy 向量化，避免逐行 Python 循环。
- 数据不足或缺列时返回中性/安全默认值，**绝不抛异常**：
  趋势/动量/量价/抄底返回 ``(50.0, ["数据不足"])``，风险返回 ``(60.0, ["数据不足"])``。
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

# 最少需要的 bar 数（与 trading_plus screener 的 20 根门槛对齐）
_MIN_BARS = 20


# ──────────────────────────────────────────────────────────────────────────
# 内部工具
# ──────────────────────────────────────────────────────────────────────────
def _f(value: object, default: float = float("nan")) -> float:
    """安全转 float：None/NaN/异常 → default。"""
    try:
        if value is None:
            return default
        out = float(value)  # type: ignore[arg-type]
        if math.isnan(out) or math.isinf(out):
            return default
        return out
    except (TypeError, ValueError):
        return default


def _col(df: pd.DataFrame, name: str) -> np.ndarray:
    """取整列为 float ndarray；列缺失返回空数组。"""
    if name not in df.columns:
        return np.empty(0, dtype=float)
    return pd.to_numeric(df[name], errors="coerce").to_numpy(dtype=float)


def _last(df: pd.DataFrame, name: str, default: float = float("nan")) -> float:
    """取某列最后一个有效值。"""
    arr = _col(df, name)
    if arr.size == 0:
        return default
    return _f(arr[-1], default)


def _clip(score: float) -> float:
    """裁剪到 [0, 100] 并 round 1 位。"""
    return round(max(0.0, min(100.0, score)), 1)


def _pct_chg_series(df: pd.DataFrame) -> np.ndarray:
    """用 close 现算涨跌幅（%），首位为 0。"""
    close = _col(df, "close")
    if close.size < 2:
        return np.zeros(close.size, dtype=float)
    out = np.zeros(close.size, dtype=float)
    prev = close[:-1]
    cur = close[1:]
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(prev > 0, (cur / prev - 1.0) * 100.0, 0.0)
    out[1:] = np.nan_to_num(ratio, nan=0.0, posinf=0.0, neginf=0.0)
    return out


# ──────────────────────────────────────────────────────────────────────────
# 1) 趋势因子
# ──────────────────────────────────────────────────────────────────────────
def score_trend(df: pd.DataFrame) -> tuple[float, list[str]]:
    """趋势因子（0-100，越高越多头）。

    考察：均线多头排列(ma5>ma10>ma20>ma60)、价>bbi、adx 趋势强度、
    macd 柱>0 且 dif>dea、dma>dma_ama、价>ma20。
    多头排列叠加强趋势约落在 80-90 区间。
    """
    if df is None or len(df) < _MIN_BARS:
        return 50.0, ["数据不足"]

    close = _last(df, "close")
    ma5 = _last(df, "ma5")
    ma10 = _last(df, "ma10")
    ma20 = _last(df, "ma20")
    ma60 = _last(df, "ma60")
    bbi = _last(df, "bbi")
    adx = _last(df, "adx")
    macd = _last(df, "macd")
    dif = _last(df, "dif")
    dea = _last(df, "dea")
    dma = _last(df, "dma")
    dma_ama = _last(df, "dma_ama")

    score = 50.0
    reasons: list[str] = []

    # 均线多头排列（核心，最高 +24）
    mas = [ma5, ma10, ma20, ma60]
    if all(not math.isnan(m) for m in mas):
        if ma5 > ma10 > ma20 > ma60:
            score += 24
            reasons.append("均线完美多头排列")
        elif ma5 > ma10 > ma20:
            score += 14
            reasons.append("短中期均线多头")
        elif ma5 < ma10 < ma20 < ma60:
            score -= 20
            reasons.append("均线空头排列")
        elif ma5 < ma10 < ma20:
            score -= 10
            reasons.append("短中期均线走弱")

    # 价 > bbi（多空生命线之上）
    if not math.isnan(close) and not math.isnan(bbi):
        if close > bbi:
            score += 8
            reasons.append("价格站上BBI")
        else:
            score -= 8
            reasons.append("价格跌破BBI")

    # 价 > ma20（中期趋势）
    if not math.isnan(close) and not math.isnan(ma20):
        if close > ma20:
            score += 6
            reasons.append("价格在MA20之上")
        else:
            score -= 6

    # adx 趋势强度
    if not math.isnan(adx):
        if adx >= 40:
            score += 12
            reasons.append(f"ADX极强趋势({adx:.0f})")
        elif adx >= 25:
            score += 8
            reasons.append(f"ADX趋势成形({adx:.0f})")
        elif adx < 18:
            score -= 4
            reasons.append(f"ADX无趋势({adx:.0f})")

    # macd 柱 + 金叉状态
    if not math.isnan(macd):
        if macd > 0:
            score += 6
            reasons.append("MACD红柱")
        else:
            score -= 6
    if not math.isnan(dif) and not math.isnan(dea):
        if dif > dea and dif > 0:
            score += 6
            reasons.append("DIF在DEA上方且>0轴")
        elif dif < dea:
            score -= 4

    # dma > dma_ama（中期动向）
    if not math.isnan(dma) and not math.isnan(dma_ama):
        if dma > dma_ama:
            score += 4
            reasons.append("DMA多头")
        else:
            score -= 4

    if not reasons:
        reasons.append("趋势中性")
    return _clip(score), reasons


# ──────────────────────────────────────────────────────────────────────────
# 2) 动量因子
# ──────────────────────────────────────────────────────────────────────────
def score_momentum(df: pd.DataFrame) -> tuple[float, list[str]]:
    """动量因子（0-100）。

    考察：kdj_j 反转区间、rsi6/rsi12 区间、roc/mtm 方向、近 5 日累计涨幅。
    超买（rsi6>80、j>100）适度减分，避免追高。
    """
    if df is None or len(df) < _MIN_BARS:
        return 50.0, ["数据不足"]

    j = _last(df, "kdj_j")
    rsi6 = _last(df, "rsi6")
    rsi12 = _last(df, "rsi12")
    roc = _last(df, "roc")
    mtm = _last(df, "mtm")

    score = 50.0
    reasons: list[str] = []

    # KDJ J 值：低位回升潜力 vs 超买
    if not math.isnan(j):
        if j < 0:
            score += 14
            reasons.append(f"J值超卖待反转({j:.1f})")
        elif j < 20:
            score += 8
            reasons.append(f"J值低位({j:.1f})")
        elif j > 100:
            score -= 14
            reasons.append(f"J值严重超买({j:.1f})")
        elif j > 90:
            score -= 6
            reasons.append(f"J值偏高({j:.1f})")

    # RSI6 强弱
    if not math.isnan(rsi6):
        if rsi6 > 80:
            score -= 12
            reasons.append(f"RSI6超买({rsi6:.0f})")
        elif rsi6 < 20:
            score += 12
            reasons.append(f"RSI6超卖({rsi6:.0f})")
        elif 50 <= rsi6 <= 70:
            score += 8
            reasons.append(f"RSI6强势({rsi6:.0f})")

    # RSI12 中期动能
    if not math.isnan(rsi12):
        if rsi12 > 50:
            score += 5
        elif rsi12 < 40:
            score -= 5

    # ROC 方向
    if not math.isnan(roc):
        if roc > 5:
            score += 8
            reasons.append(f"ROC动量强({roc:.1f})")
        elif roc > 0:
            score += 4
        elif roc < -5:
            score -= 8
            reasons.append(f"ROC动量弱({roc:.1f})")

    # MTM 方向
    if not math.isnan(mtm):
        if mtm > 0:
            score += 4
        else:
            score -= 4

    # 近 5 日累计涨幅
    pct = _pct_chg_series(df)
    if pct.size >= 5:
        recent5 = float(np.sum(pct[-5:]))
        if recent5 > 12:
            score += 6
            reasons.append(f"近5日累涨{recent5:.0f}%")
        elif recent5 > 3:
            score += 3
        elif recent5 < -12:
            score -= 8
            reasons.append(f"近5日累跌{recent5:.0f}%")

    if not reasons:
        reasons.append("动量中性")
    return _clip(score), reasons


# ──────────────────────────────────────────────────────────────────────────
# 3) 量价因子
# ──────────────────────────────────────────────────────────────────────────
def score_volume(df: pd.DataFrame) -> tuple[float, list[str]]:
    """量价因子（0-100）。

    考察：volume 相对 mavol5/mavol10 的量比；价涨量增=攻击形态加分；
    价跌量增=出货减分；缩量企稳加分；obv 趋势。
    复刻 trading_plus screener.score_volume_pattern 的精神。
    """
    if df is None or len(df) < _MIN_BARS:
        return 50.0, ["数据不足"]

    vol = _last(df, "volume")
    mavol5 = _last(df, "mavol5")
    mavol10 = _last(df, "mavol10")
    pct = _pct_chg_series(df)
    today_pct = float(pct[-1]) if pct.size else 0.0

    score = 50.0
    reasons: list[str] = []

    # 量比（相对 5 日均量）
    vol_ratio = float("nan")
    if not math.isnan(vol) and not math.isnan(mavol5) and mavol5 > 0:
        vol_ratio = vol / mavol5
        if vol_ratio >= 2.0:
            score += 16
            reasons.append(f"倍量(量比{vol_ratio:.1f})")
        elif vol_ratio >= 1.5:
            score += 8
            reasons.append(f"放量(量比{vol_ratio:.1f})")
        elif vol_ratio <= 0.5:
            score += 8
            reasons.append(f"缩量企稳(量比{vol_ratio:.1f})")
        elif vol_ratio <= 0.7:
            score += 4
            reasons.append("温和缩量")

    # 涨跌与量能配合
    if not math.isnan(vol_ratio):
        if today_pct > 3 and vol_ratio > 1.2:
            score += 16
            reasons.append("价涨量增(攻击形态)")
        elif today_pct < -3 and vol_ratio > 1.2:
            score -= 18
            reasons.append("价跌量增(出货嫌疑)")
        elif today_pct < 0 and vol_ratio <= 0.7:
            score += 8
            reasons.append("缩量回调(健康)")
        elif today_pct > 0 and 0.7 < vol_ratio < 1.2:
            score += 4
            reasons.append("价涨量平")

    # 5 日量 vs 10 日量趋势（量能温和放大）
    if not math.isnan(mavol5) and not math.isnan(mavol10) and mavol10 > 0:
        if 1.0 < mavol5 / mavol10 <= 1.5:
            score += 4
            reasons.append("量能温和放大")
        elif mavol5 / mavol10 > 2.0:
            score -= 4
            reasons.append("量能急剧放大(警惕)")

    # OBV 趋势（近 10 日）
    obv = _col(df, "obv")
    if obv.size >= 10:
        if obv[-1] > obv[-10]:
            score += 6
            reasons.append("OBV资金流入")
        elif obv[-1] < obv[-10]:
            score -= 6
            reasons.append("OBV资金流出")

    if not reasons:
        reasons.append("量价中性")
    return _clip(score), reasons


# ──────────────────────────────────────────────────────────────────────────
# 4) 抄底/BD 因子
# ──────────────────────────────────────────────────────────────────────────
def score_dip(df: pd.DataFrame) -> tuple[float, list[str]]:
    """抄底/BD 因子（0-100，越高越具低吸价值）。

    考察：kdj_j 极低、close 靠近 boll_dn/近 20 日支撑（枢轴邻近）、rsi6 超卖、
    缩量回调、price<bbi 低位。复刻 trading_plus screener.score_bd_opportunity 的精神。
    """
    if df is None or len(df) < _MIN_BARS:
        return 50.0, ["数据不足"]

    close = _last(df, "close")
    j = _last(df, "kdj_j")
    bbi = _last(df, "bbi")
    rsi6 = _last(df, "rsi6")
    boll_dn = _last(df, "boll_dn")
    vol = _last(df, "volume")
    mavol5 = _last(df, "mavol5")
    wr6 = _last(df, "wr6")

    low = _col(df, "low")
    support = float(np.min(low[-20:])) if low.size >= 20 else float("nan")

    # 抄底分从 30 起步（中性偏低，需信号累积才高）
    score = 30.0
    reasons: list[str] = []

    # J 值（核心，对齐 score_bd_opportunity）
    if not math.isnan(j):
        if j < -15:
            score += 30
            reasons.append(f"J值极低({j:.1f})")
        elif j < -10:
            score += 22
            reasons.append(f"J值深度超卖({j:.1f})")
        elif j < 0:
            score += 14
            reasons.append(f"J值超卖({j:.1f})")
        elif j > 50:
            score -= 12

    # RSI6 超卖
    if not math.isnan(rsi6):
        if rsi6 < 15:
            score += 12
            reasons.append(f"RSI6极度超卖({rsi6:.0f})")
        elif rsi6 < 25:
            score += 8
            reasons.append(f"RSI6超卖({rsi6:.0f})")
        elif rsi6 > 60:
            score -= 8

    # WR6 超卖（>80 为超卖区）
    if not math.isnan(wr6) and wr6 > 80:
        score += 6
        reasons.append("WR6超卖区")

    # 靠近布林下轨
    if not math.isnan(close) and not math.isnan(boll_dn) and boll_dn > 0:
        if close <= boll_dn * 1.01:
            score += 12
            reasons.append("贴近布林下轨")
        elif close <= boll_dn * 1.03:
            score += 6
            reasons.append("接近布林下轨")

    # 枢轴邻近：靠近近 20 日支撑
    if not math.isnan(close) and not math.isnan(support) and support > 0:
        dist = (close - support) / support
        if dist <= 0.02:
            score += 12
            reasons.append("贴近20日支撑")
        elif dist <= 0.05:
            score += 6
            reasons.append("接近20日支撑")

    # 缩量回调（量 < 5 日均量 0.6）
    if not math.isnan(vol) and not math.isnan(mavol5) and mavol5 > 0:
        if vol < mavol5 * 0.6:
            score += 10
            reasons.append("缩量回调")

    # BBI 下方低位
    if not math.isnan(close) and not math.isnan(bbi):
        if close < bbi:
            score += 8
            reasons.append("BBI下方低位")
        elif close > bbi * 1.05:
            score -= 12
            reasons.append("远离BBI(非低吸位)")

    if not reasons:
        reasons.append("无明显低吸信号")
    return _clip(score), reasons


# ──────────────────────────────────────────────────────────────────────────
# 5) 风险因子（安全分，100=最安全）
# ──────────────────────────────────────────────────────────────────────────
def score_risk(df: pd.DataFrame) -> tuple[float, list[str]]:
    """风险安全分（0-100，越高越安全）。

    从 100 起扣分：近高点（距 60/240 日高 < 10%）、跌破 bbi、连续下跌、
    放量阴线、高位放量。warnings 记录扣分原因。
    复刻 trading_plus screener.score_risk 的精神。
    """
    if df is None or len(df) < _MIN_BARS:
        return 60.0, ["数据不足"]

    close = _last(df, "close")
    bbi = _last(df, "bbi")
    high = _col(df, "high")
    closes = _col(df, "close")
    vols = _col(df, "volume")
    pct = _pct_chg_series(df)

    score = 100.0
    warnings: list[str] = []

    # 近高点风险：距 60 日高点
    if high.size >= 60 and not math.isnan(close):
        max60 = float(np.max(high[-60:]))
        if max60 > 0:
            drop = (max60 - close) / max60
            if drop < 0.10:
                score -= 30
                warnings.append("接近60日高位")
            elif drop < 0.20:
                score -= 15
                warnings.append("相对60日高位")

    # 距 240 日（长期）高点
    if high.size >= 240 and not math.isnan(close):
        max240 = float(np.max(high[-240:]))
        if max240 > 0 and (max240 - close) / max240 < 0.10:
            score -= 12
            warnings.append("接近240日高位")

    # 跌破 BBI
    if not math.isnan(close) and not math.isnan(bbi) and close < bbi:
        score -= 20
        warnings.append("跌破BBI")

    # 放量阴线（近 5 日内出现）：跌 + 量 > 前日 1.5 倍
    if closes.size >= 2 and vols.size >= 2:
        n = closes.size
        lookback = min(5, n - 1)
        for k in range(1, lookback + 1):
            i = n - k
            if i - 1 < 0:
                break
            if closes[i] < closes[i - 1] and vols[i - 1] > 0 and vols[i] > vols[i - 1] * 1.5:
                score -= 10
                warnings.append("近期放量阴线")
                break

    # 连续 3 日下跌
    if pct.size >= 3 and np.all(pct[-3:] < 0):
        score -= 15
        warnings.append("连续3日下跌")

    # 高位放量（近高点 + 当日放量）：可能见顶派发
    if high.size >= 60 and vols.size >= 6 and not math.isnan(close):
        max60 = float(np.max(high[-60:]))
        avg5 = float(np.mean(vols[-6:-1])) if vols.size >= 6 else float("nan")
        if (
            max60 > 0
            and (max60 - close) / max60 < 0.10
            and not math.isnan(avg5)
            and avg5 > 0
            and vols[-1] > avg5 * 2.0
        ):
            score -= 12
            warnings.append("高位放量")

    if not warnings:
        warnings.append("无明显风险")
    return _clip(score), warnings


# ──────────────────────────────────────────────────────────────────────────
# 因子元数据（供前端 & 评分引擎默认权重）
# ──────────────────────────────────────────────────────────────────────────
FACTOR_DEFS: list[dict] = [
    {
        "key": "trend",
        "label": "趋势",
        "default_weight": 0.25,
        "desc": "均线多头排列、价站BBI/MA20、ADX趋势强度、MACD与DMA方向",
    },
    {
        "key": "momentum",
        "label": "动量",
        "default_weight": 0.20,
        "desc": "KDJ_J反转区、RSI6/RSI12区间、ROC/MTM方向、近5日累计涨幅",
    },
    {
        "key": "volume",
        "label": "量价",
        "default_weight": 0.20,
        "desc": "量比、价涨量增攻击/价跌量增出货、缩量企稳、OBV资金流向",
    },
    {
        "key": "dip",
        "label": "抄底",
        "default_weight": 0.20,
        "desc": "J值极低、贴近布林下轨/20日支撑、RSI6超卖、缩量回调、BBI下方低位",
    },
    {
        "key": "risk",
        "label": "风险",
        "default_weight": 0.15,
        "desc": "安全分(100最安全)：近高点、跌破BBI、连续下跌、放量阴线、高位放量扣分",
    },
]


__all__ = [
    "score_trend",
    "score_momentum",
    "score_volume",
    "score_dip",
    "score_risk",
    "FACTOR_DEFS",
]
