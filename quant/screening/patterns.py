"""trading_plus 高级形态移植（向量化 / 快照）。

本模块把 trading_plus/modules/indicators 中的高级形态算法重写为作用于 quant
预计算 DataFrame 的快照函数。语义与原实现逐条对齐（阈值、分支、评分），
但用 numpy 向量化、避免逐行 Python 循环（状态机/历史滚动除外）。

约定：
- 入参 ``df`` 为升序（按 ``dt``）DataFrame，含 OHLCV 与 20 指标全列。
- ``df`` 无 ``pct_chg`` 列 —— 需要时用 ``close.pct_change()*100`` 现算。
- 所有函数对「最后一根 bar」做快照判断；数据不足时返回中性/安全默认值，绝不抛异常。

"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


# ====================================================================
# 基础 helper（numpy 向量化）
# ====================================================================


def slope(values: np.ndarray, period: int) -> float:
    """通达信 SLOPE 线性回归斜率（每 bar 变化量）。

    period>len 时取 len，<2 返回 0。
    x = 0..n-1，slope = (n*Σxy - Σx*Σy) / (n*Σx² - (Σx)²)。

    与 trading_plus core.calculate_slope 对齐。
    """
    arr = np.asarray(values, dtype=float).ravel()
    n = len(arr)
    if period > n:
        period = n
    if period < 2:
        return 0.0

    recent = arr[-period:]
    nn = period
    x = np.arange(nn, dtype=float)
    sum_x = nn * (nn - 1) / 2.0
    sum_xx = (nn - 1) * nn * (2 * nn - 1) / 6.0
    sum_y = float(recent.sum())
    sum_xy = float((recent * x).sum())

    denominator = nn * sum_xx - sum_x * sum_x
    if denominator == 0:
        return 0.0
    return (nn * sum_xy - sum_x * sum_y) / denominator


def _ma_last(prices: np.ndarray, period: int) -> float:
    """复刻 core.calculate_ma：取最后 period 个的简单均值；``len<period`` 返回 0。"""
    arr = np.asarray(prices, dtype=float).ravel()
    if len(arr) < period:
        return 0.0
    return float(arr[-period:].mean())


def _pct_chg(close: np.ndarray) -> np.ndarray:
    """现算涨跌幅 (%) = close.pct_change()*100，首位为 0（NaN→0）。"""
    s = pd.Series(np.asarray(close, dtype=float).ravel())
    return (s.pct_change() * 100).fillna(0.0).to_numpy()


# ====================================================================
# 沙漏评分 V9
# ====================================================================


def sandglass_score(df: pd.DataFrame) -> dict:
    """沙漏评分 V9，5 因子各 0-20（缩量收敛/枢轴邻近/量能斜率/均线结构/事件风险）。

    复刻 trading_plus price_patterns.calculate_sandglass_score 逐条阈值。
    用 df 的 close/volume/high/low；ma5/ma10/ma20 用 close 现算（与原版一致）。
    len<20 → 零分。

    返回 {'score':int, 'rating':str('极佳/良好/一般/较差/极差'),
          'factors':dict, 'is_perfect':bool(score>=80)}。
    """
    result: dict[str, Any] = {
        "score": 0,
        "rating": "极差",
        "factors": {},
        "is_perfect": False,
    }

    n = len(df)
    if n < 20:
        return result

    closes = df["close"].to_numpy(dtype=float)
    volumes = df["volume"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    opens = df["open"].to_numpy(dtype=float)
    pct = _pct_chg(closes)

    # ========== 因子 1：缩量/收敛 (0-20) ==========
    vol_ma10 = float(volumes[-10:].mean())
    vol_ma20 = float(volumes[-20:].mean())

    vol_ratio = vol_ma10 / vol_ma20 if vol_ma20 > 0 else 1.0
    if vol_ratio < 0.6:
        score_contraction_a = 12
    elif vol_ratio < 0.8:
        score_contraction_a = 8
    elif vol_ratio < 1.0:
        score_contraction_a = 4
    else:
        score_contraction_a = 0

    recent_5_vol = volumes[-5:]
    prev_5_vol = volumes[-10:-5]
    vol_range_recent = float(recent_5_vol.max() - recent_5_vol.min())
    vol_range_prev = float(prev_5_vol.max() - prev_5_vol.min()) if len(prev_5_vol) else vol_range_recent

    vol_range_ratio = vol_range_recent / vol_range_prev if vol_range_prev > 0 else 1.0
    if vol_range_ratio < 0.5:
        score_contraction_b = 8
    elif vol_range_ratio < 0.8:
        score_contraction_b = 5
    elif vol_range_ratio < 1.0:
        score_contraction_b = 3
    else:
        score_contraction_b = 0

    score_contraction = min(20, score_contraction_a + score_contraction_b)

    # ========== 因子 2：枢轴邻近 (0-20) ==========
    support = float(lows[-20:].min())
    current_price = float(closes[-1])
    distance_pct = (current_price - support) / support if support > 0 else 1.0
    if distance_pct <= 0.03:
        score_pivot = 20
    elif distance_pct <= 0.05:
        score_pivot = 16
    elif distance_pct <= 0.08:
        score_pivot = 12
    elif distance_pct <= 0.10:
        score_pivot = 8
    elif distance_pct <= 0.15:
        score_pivot = 4
    else:
        score_pivot = 0

    # ========== 因子 3：量能斜率 (0-20) ==========
    vol_slope = slope(volumes[-10:], 10) if len(volumes) >= 10 else 0.0
    slope_normalized = vol_slope / vol_ma10 if vol_ma10 > 0 else 0.0
    if -0.05 <= slope_normalized <= -0.01:
        score_vol_slope = 20
    elif -0.10 <= slope_normalized < -0.05:
        score_vol_slope = 15
    elif -0.01 < slope_normalized <= 0.02:
        score_vol_slope = 12
    elif -0.15 <= slope_normalized < -0.10:
        score_vol_slope = 8
    elif slope_normalized > 0.05:
        score_vol_slope = 2
    else:
        score_vol_slope = 5

    # ========== 因子 4：均线结构 (0-20) ==========
    ma5 = _ma_last(closes, 5)
    ma10 = _ma_last(closes, 10)
    ma20 = _ma_last(closes, 20)

    score_ma = 0
    if ma5 > ma10 > ma20:
        score_ma += 10
    elif ma5 > ma10 or ma10 > ma20:
        score_ma += 5

    if ma20 > 0 and current_price > ma20:
        score_ma += 4

    if ma20 > 0:
        ma_gap = abs(ma5 - ma20) / ma20
        if ma_gap < 0.02:
            score_ma += 6
        elif ma_gap < 0.05:
            score_ma += 4
        elif ma_gap < 0.08:
            score_ma += 2

    score_ma = min(20, score_ma)

    # ========== 因子 5：事件风险 (0-20，从 20 分起扣) ==========
    score_risk = 20

    # 检查 1：近 5 天大幅跳空下跌
    for i in range(max(0, n - 5), n):
        if i > 0:
            gap_down = (opens[i] - closes[i - 1]) / closes[i - 1] if closes[i - 1] != 0 else 0.0
            if gap_down < -0.03:
                score_risk -= 10
                break

    # 检查 2：连续 3 天以上下跌
    down_count = 0
    for i in range(max(0, n - 5), n):
        if pct[i] < 0:
            down_count += 1
        else:
            down_count = 0
    if down_count >= 3:
        score_risk -= 5

    # 检查 3：放量不涨（量增价滞）
    if n >= 5:
        recent_vol_spike = volumes[-1] > vol_ma10 * 1.8
        price_no_rise = closes[-1] <= closes[-2] if n >= 2 else False
        if recent_vol_spike and price_no_rise:
            score_risk -= 5

    # 检查 4：近 52 周高点（距 240 天最高价 < 5%）
    lookback_52w = min(240, n)
    high_52w = float(highs[-lookback_52w:].max())
    if high_52w > 0 and (high_52w - current_price) / high_52w < 0.05:
        score_risk -= 5

    score_risk = max(0, score_risk)

    # ========== 汇总 ==========
    total_score = score_contraction + score_pivot + score_vol_slope + score_ma + score_risk
    total_score = max(0, min(100, total_score))

    if total_score >= 80:
        rating = "极佳"
    elif total_score >= 65:
        rating = "良好"
    elif total_score >= 45:
        rating = "一般"
    elif total_score >= 25:
        rating = "较差"
    else:
        rating = "极差"

    result["score"] = int(total_score)
    result["rating"] = rating
    result["factors"] = {
        "缩量收敛": score_contraction,
        "枢轴邻近": score_pivot,
        "量能斜率": score_vol_slope,
        "均线结构": score_ma,
        "事件风险": score_risk,
    }
    result["is_perfect"] = total_score >= 80
    return result


# ====================================================================
# 蜈蚣图
# ====================================================================


def centipede(df: pd.DataFrame) -> dict:
    """蜈蚣图，5 因子各 0-20（长上影/长下影/十字星/量能CV/价格无趋势），近 20 根。

    复刻 trading_plus price_patterns.detect_centipede_pattern。
    返回 {'is_centipede':bool(score>=60), 'score':int, 'factors':dict}。
    """
    result: dict[str, Any] = {
        "is_centipede": False,
        "score": 0,
        "factors": {},
    }

    if len(df) < 20:
        return result

    recent = df.iloc[-20:]
    closes = recent["close"].to_numpy(dtype=float)
    opens = recent["open"].to_numpy(dtype=float)
    highs = recent["high"].to_numpy(dtype=float)
    lows = recent["low"].to_numpy(dtype=float)
    volumes = recent["volume"].to_numpy(dtype=float)
    # pct_chg 现算（用整列 close 算后取最后 20 个，保证与逐 bar pct_change 对齐）
    pct_full = _pct_chg(df["close"].to_numpy(dtype=float))
    pcts = pct_full[-20:]

    factor_scores: dict[str, int] = {}

    body = np.abs(closes - opens)

    # --- 因子1：长上影线比例 ---
    upper_shadow = highs - closes
    upper_days = int(np.sum((body > 0) & (upper_shadow > 2 * body)))
    upper_ratio = upper_days / 20
    if upper_ratio > 0.4:
        factor_scores["长上影线"] = 20
    elif upper_ratio > 0.25:
        factor_scores["长上影线"] = 10
    else:
        factor_scores["长上影线"] = 0

    # --- 因子2：长下影线比例 ---
    lower_shadow = closes - lows
    lower_days = int(np.sum((body > 0) & (lower_shadow > 2 * body)))
    lower_ratio = lower_days / 20
    if lower_ratio > 0.4:
        factor_scores["长下影线"] = 20
    elif lower_ratio > 0.25:
        factor_scores["长下影线"] = 10
    else:
        factor_scores["长下影线"] = 0

    # --- 因子3：十字星比例 ---
    with np.errstate(divide="ignore", invalid="ignore"):
        body_pct = np.where(opens > 0, np.abs(closes - opens) / opens, 1.0)
    doji_days = int(np.sum((opens > 0) & (body_pct < 0.01)))
    doji_ratio = doji_days / 20
    if doji_ratio > 0.3:
        factor_scores["十字星"] = 20
    elif doji_ratio > 0.15:
        factor_scores["十字星"] = 10
    else:
        factor_scores["十字星"] = 0

    # --- 因子4：量能无规律（变异系数） ---
    vol_mean = float(volumes.mean())
    if vol_mean > 0:
        vol_std = float(np.sqrt(np.mean((volumes - vol_mean) ** 2)))
        vol_cv = vol_std / vol_mean
    else:
        vol_cv = 0.0
    if vol_cv > 0.8:
        factor_scores["量能无规律"] = 20
    elif vol_cv > 0.5:
        factor_scores["量能无规律"] = 10
    else:
        factor_scores["量能无规律"] = 0

    # --- 因子5：价格无趋势（窄幅震荡 + 高波动） ---
    total_change = (closes[-1] - opens[0]) / opens[0] if opens[0] > 0 else 0.0
    pct_mean = float(pcts.mean())
    pct_std = float(np.sqrt(np.mean((pcts - pct_mean) ** 2)))
    is_range_bound = abs(total_change) < 0.05
    is_volatile = pct_std > 2.0
    if is_range_bound and is_volatile:
        factor_scores["价格无趋势"] = 20
    elif is_range_bound or is_volatile:
        factor_scores["价格无趋势"] = 10
    else:
        factor_scores["价格无趋势"] = 0

    total_score = int(sum(factor_scores.values()))
    result["score"] = total_score
    result["factors"] = factor_scores
    result["is_centipede"] = total_score >= 60
    return result


# ====================================================================
# 三波理论
# ====================================================================


def _find_recent_low(lows: np.ndarray, window: int = 5) -> tuple[int, float]:
    """找近期低点（复刻 wave_theory._find_recent_low）。

    数据不足（len < window*2+1）时返回全局最低；否则从后往前找局部最小值。
    """
    n = len(lows)
    if n < window * 2 + 1:
        idx = int(np.argmin(lows))
        return idx, float(lows[idx])

    for i in range(n - window - 1, window - 1, -1):
        current_low = lows[i]
        is_local_min = True
        for j in range(i - window, i + window + 1):
            if j == i:
                continue
            if lows[j] < current_low:
                is_local_min = False
                break
        if is_local_min:
            return i, float(current_low)

    idx = int(np.argmin(lows))
    return idx, float(lows[idx])


def three_waves(df: pd.DataFrame) -> dict:
    """三波理论：建仓波/拉升波/冲刺波/未知。

    复刻 trading_plus wave_theory.detect_three_waves。
    需要 pct_chg：用 close.pct_change()*100 现算（df 无 pct_chg 列）。len<30 → 未知。

    返回 {'wave':str, 'confidence':float, 'stats':dict,
          'bd_suggestion':str('可干/等回调/不看/观望')}。
    """
    result: dict[str, Any] = {
        "wave": "未知",
        "confidence": 0.0,
        "stats": {},
        "bd_suggestion": "观望",
    }

    n = len(df)
    if n < 30:
        return result

    closes = df["close"].to_numpy(dtype=float)
    opens = df["open"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    pct = _pct_chg(closes)

    low_idx, low_price = _find_recent_low(lows, window=5)
    if low_idx >= n - 1:
        return result

    today_close = float(closes[-1])
    days_from_low = (n - low_idx) - 1

    seg_highs = highs[low_idx:]
    high_price = float(seg_highs.max())
    gain_pct = (today_close / low_price - 1) * 100 if low_price > 0 else 0.0

    # 涨停次数（low_idx 到今日，pct_chg>=9.9）
    limit_up_count = int(np.sum(pct[low_idx:] >= 9.9))

    # 阳线占比（close>open）
    seg_close = closes[low_idx:]
    seg_open = opens[low_idx:]
    red_ratio = float(np.mean(seg_close > seg_open)) if len(seg_close) else 0.0

    # 日均涨幅
    seg = closes[low_idx:]
    if len(seg) >= 2:
        total_gain = (seg[-1] / seg[0] - 1) * 100
        avg_daily_gain = total_gain / len(seg)
    else:
        avg_daily_gain = 0.0

    # 20 日涨幅
    gain_20day = (closes[-1] / closes[-20] - 1) * 100 if n >= 20 else 0.0

    stats = {
        "low_price": round(low_price, 2),
        "high_price": round(high_price, 2),
        "gain_pct": round(gain_pct, 2),
        "limit_up_count": limit_up_count,
        "red_ratio": round(red_ratio, 2),
        "avg_daily_gain": round(avg_daily_gain, 2),
        "gain_20day": round(gain_20day, 2),
        "days_from_low": days_from_low,
    }
    result["stats"] = stats

    # ========== 冲刺波 ==========
    sprint_score = 0
    if gain_pct > 100:
        sprint_score += 40
    if limit_up_count >= 3:
        sprint_score += 30
    if gain_20day > 30:
        sprint_score += 20
    if red_ratio > 0.7:
        sprint_score += 10

    if sprint_score >= 60:
        result["wave"] = "冲刺波"
        result["confidence"] = round(min(sprint_score / 100, 1.0), 2)
        result["bd_suggestion"] = "不看"
        return result

    # ========== 拉升波 ==========
    pull_score = 0
    if gain_pct > 50:
        pull_score += 35
    elif gain_pct > 40:
        pull_score += 20
    if gain_20day > 30:
        pull_score += 25
    elif gain_20day > 20:
        pull_score += 15
    if limit_up_count >= 2:
        pull_score += 25
    elif limit_up_count >= 1:
        pull_score += 10
    if avg_daily_gain > 1.5:
        pull_score += 15

    if pull_score >= 50:
        result["wave"] = "拉升波"
        result["confidence"] = round(min(pull_score / 100, 1.0), 2)
        result["bd_suggestion"] = "等回调"
        return result

    # ========== 建仓波 ==========
    build_score = 0
    if 25 <= gain_pct <= 50:
        build_score += 35
    elif 15 <= gain_pct < 25:
        build_score += 20
    elif 50 < gain_pct <= 60:
        build_score += 15
    if limit_up_count <= 1:
        build_score += 25
    if red_ratio > 0.6:
        build_score += 20
    elif red_ratio > 0.5:
        build_score += 10
    if 0.3 <= avg_daily_gain <= 2.0:
        build_score += 20

    if build_score >= 50:
        result["wave"] = "建仓波"
        result["confidence"] = round(min(build_score / 100, 1.0), 2)
        result["bd_suggestion"] = "可干"
        return result

    result["confidence"] = round(max(sprint_score, pull_score, build_score) / 100, 2)
    return result


# ====================================================================
# 麒麟会四阶段
# ====================================================================


def _kirin_n_shape(lows: np.ndarray) -> bool:
    """N 型逐步抬高检测（复刻 kirin_detector._detect_n_shape_raise）。

    找局部低点（low[i]<low[i-1] 且 low[i]<low[i+1]），取最近 3 个判断逐步抬高。
    """
    n = len(lows)
    if n < 20:
        return False
    lows_idx = []
    for i in range(5, n - 5):
        if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
            lows_idx.append((i, float(lows[i])))
    if len(lows_idx) < 3:
        return False
    recent = lows_idx[-3:]
    if recent[0][1] < recent[1][1] * 1.02 and recent[1][1] < recent[2][1] * 1.02:
        return True
    return False


def _kirin_chuhuo_score(df: pd.DataFrame) -> int:
    """出货信号简化评分（用于派发阶段加分）。

    trading_plus 派发评分调用 detect_chuhuo_wushi 并在 total_score>=2 时加 30 分。
    此处用与「出货五式」精神一致的近 5 日量价背离计数近似（高位放量阴线 / 上影 / 滞涨）。
    返回近似 total_score。

    与原版 detect_chuhuo_wushi 的激活域对齐：要求 len>=20 且处于相对高位
    （收盘 >= 近 20 日高点 × 0.85），否则返回 0 —— 出货只发生在高位，
    避免低位股误得派发加分。
    """
    n = len(df)
    if n < 20:
        return 0
    closes = df["close"].to_numpy(dtype=float)
    opens = df["open"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    volumes = df["volume"].to_numpy(dtype=float)
    pct = _pct_chg(closes)

    # 高位门槛（对齐 detect_chuhuo_wushi）：当前收盘必须接近近 20 日高点
    recent_high_20 = float(highs[-20:].max())
    if recent_high_20 <= 0 or closes[-1] < recent_high_20 * 0.85:
        return 0

    score = 0
    vol_ma5 = float(volumes[-6:-1].mean()) if n >= 6 else float(volumes.mean())
    # 式一：放量阴线（量 > 5日均量*1.2 且收阴）
    if volumes[-1] > vol_ma5 * 1.2 and closes[-1] < opens[-1]:
        score += 1
    # 式二：长上影线
    body = abs(closes[-1] - opens[-1])
    upper = highs[-1] - max(closes[-1], opens[-1])
    if body > 0 and upper > 2 * body:
        score += 1
    # 式三：放量滞涨（量增价跌/平）
    if volumes[-1] > vol_ma5 * 1.5 and pct[-1] <= 0:
        score += 1
    return score


def kirin_stage(df: pd.DataFrame) -> dict:
    """麒麟会四阶段：吸筹/拉升/派发/回落/未知。

    复刻 trading_plus kirin_detector.detect_kirin_stage 评分制（取最高分）。
    len<60 → 未知。pct_chg 现算；涨停判定 pct_chg>=9.9。

    返回 {'stage','confidence','sub_type','scores':dict,'indicators':dict,'operation':str}。
    """
    result: dict[str, Any] = {
        "stage": "未知",
        "confidence": 0.0,
        "sub_type": "未知",
        "scores": {},
        "indicators": {},
        "operation": "观望",
    }

    n = len(df)
    if n < 60:
        return result

    closes = df["close"].to_numpy(dtype=float)
    opens = df["open"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    volumes = df["volume"].to_numpy(dtype=float)
    pct = _pct_chg(closes)

    # ===== 价格位置（120 日区间） =====
    period = min(120, n)
    seg_low = float(lows[-period:].min())
    seg_high = float(highs[-period:].max())
    current = float(closes[-1])
    if seg_high > seg_low:
        from_low_pct = (current - seg_low) / (seg_high - seg_low) * 100
        from_high_pct = (seg_high - current) / (seg_high - seg_low) * 100
    else:
        from_low_pct = 50.0
        from_high_pct = 50.0

    # ===== 红肥绿瘦 ratio（近 20 日 阳量/阴量） =====
    seg20 = slice(max(0, n - 20), n)
    c20 = closes[seg20]
    o20 = opens[seg20]
    v20 = volumes[seg20]
    red_vol = float(v20[c20 > o20].sum())
    green_vol = float(v20[c20 < o20].sum())
    if green_vol <= 0:
        red_green = 3.0
    else:
        red_green = red_vol / green_vol

    # ===== N 型抬高 =====
    n_shape = _kirin_n_shape(lows)

    # ===== 呼吸节奏健康（近 10 日 上涨日均量 > 下跌日均量*1.2） =====
    c10 = closes[-10:]
    o10 = opens[-10:]
    v10 = volumes[-10:]
    up_v = v10[c10 > o10]
    down_v = v10[c10 < o10]
    if len(up_v) == 0 or len(down_v) == 0:
        breathing = False
    else:
        breathing = float(up_v.mean()) > float(down_v.mean()) * 1.2

    # ===== 拉升速度（近 20 日涨幅） =====
    pull_speed = (closes[-1] / closes[-20] - 1) * 100 if n >= 20 else 0.0

    # ===== 量价齐升 =====
    if n >= 10:
        recent_5_close = float(closes[-5:].mean())
        prev_5_close = float(closes[-10:-5].mean())
        recent_5_vol = float(volumes[-5:].mean())
        prev_5_vol = float(volumes[-10:-5].mean())
        vol_price_rise = recent_5_close > prev_5_close and recent_5_vol > prev_5_vol
    else:
        vol_price_rise = False

    # ===== 涨停次数（近 20 日） =====
    seg_days = min(20, n)
    limit_up_count = int(np.sum(pct[-seg_days:] >= 9.9))
    has_limit_up = limit_up_count > 0

    # ===== 量能水平 =====
    avg_vol_60 = float(volumes[-60:].mean()) if n >= 60 else float(volumes.mean())
    recent_avg_vol = float(volumes[-10:].mean())
    is_high_vol = recent_avg_vol > avg_vol_60 * 1.3 if avg_vol_60 > 0 else False
    is_low_vol = recent_avg_vol < avg_vol_60 * 0.8 if avg_vol_60 > 0 else False

    if from_low_pct < 30:
        price_pos = "低位"
    elif from_low_pct > 70:
        price_pos = "高位"
    else:
        price_pos = "中位"

    if is_high_vol:
        vol_pattern = "放量"
    elif is_low_vol:
        vol_pattern = "缩量"
    else:
        vol_pattern = "正常"

    indicators = {
        "price_position": price_pos,
        "vol_pattern": vol_pattern,
        "red_green_ratio": round(red_green, 2),
        "n_shape": n_shape,
        "healthy_breathing": breathing,
        "pull_speed": round(pull_speed, 2),
        "limit_up_count": limit_up_count,
        "from_low_pct": round(from_low_pct, 1),
        "from_high_pct": round(from_high_pct, 1),
    }
    result["indicators"] = indicators

    # ========== 吸筹评分 ==========
    xishou_score = 0
    if from_low_pct < 30:
        xishou_score += 30
    elif from_low_pct < 50:
        xishou_score += 15
    if is_high_vol:
        xishou_score += 20
    if n_shape:
        xishou_score += 20
    if red_green > 1.3:
        xishou_score += 20
    elif red_green > 1.0:
        xishou_score += 10
    if not has_limit_up:
        xishou_score += 10

    # ========== 拉升评分 ==========
    lasheng_score = 0
    if from_low_pct > 30:
        lasheng_score += 20
    elif from_low_pct > 20:
        lasheng_score += 10
    if pull_speed > 30:
        lasheng_score += 25
    elif pull_speed > 20:
        lasheng_score += 15
    if limit_up_count >= 2:
        lasheng_score += 20
    elif has_limit_up:
        lasheng_score += 10
    if vol_price_rise:
        lasheng_score += 15
    if breathing:
        lasheng_score += 10

    # ========== 派发评分 ==========
    paifa_score = 0
    if from_high_pct < 15:
        paifa_score += 30
    elif from_high_pct < 30:
        paifa_score += 15
    if is_high_vol and from_low_pct > 60:
        paifa_score += 20
    if red_green < 0.7:
        paifa_score += 20
    elif red_green < 1.0:
        paifa_score += 10
    if _kirin_chuhuo_score(df) >= 2:
        paifa_score += 30

    # ========== 回落评分 ==========
    luoluo_score = 0
    if from_high_pct > 20:
        luoluo_score += 30
    elif from_high_pct > 10:
        luoluo_score += 15
    if is_low_vol:
        luoluo_score += 25
    recent_red = int(np.sum(c10 > o10))
    if recent_red < 3:
        luoluo_score += 20
    if not has_limit_up:
        luoluo_score += 10

    scores = {
        "xishou": xishou_score,
        "lasheng": lasheng_score,
        "paifa": paifa_score,
        "luoluo": luoluo_score,
    }
    result["scores"] = scores

    max_score = max(scores.values())
    if max_score < 30:
        result["stage"] = "未知"
        result["confidence"] = round(max_score / 100, 2)
        result["operation"] = "观望"
        return result

    stage_map = {
        "xishou": ("吸筹", "关注，等BD"),
        "lasheng": ("拉升", "不追，等回调BD"),
        "paifa": ("派发", "准备走人"),
        "luoluo": ("回落", "不抄底"),
    }

    max_stage = max(scores, key=lambda k: scores[k])
    result["stage"] = stage_map[max_stage][0]
    result["confidence"] = round(min(max_score / 100, 1.0), 2)
    result["operation"] = stage_map[max_stage][1]

    # ========== 子类型判断 ==========
    if result["stage"] == "拉升":
        if pull_speed > 40:
            result["sub_type"] = "铁蝴蝶"
        elif pull_speed < 25 and breathing:
            result["sub_type"] = "学院派铁蝴蝶"
        else:
            result["sub_type"] = "铁蝴蝶"
    elif result["stage"] == "派发":
        recent_drop = (closes[-1] / closes[-5] - 1) * 100 if n >= 5 else 0.0
        if recent_drop < -15:
            result["sub_type"] = "铁蝴蝶"
        else:
            result["sub_type"] = "学院派铁蝴蝶"

    return result
