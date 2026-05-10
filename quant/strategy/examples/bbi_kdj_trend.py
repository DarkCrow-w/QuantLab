"""
BBI趋势 + KDJ择时 策略

核心思想: BBI定方向, KDJ定时机, ATR管风控

买入条件（全部满足）:
  1. BBI上升趋势: BBI > N天前BBI, 且收盘价在BBI上方
  2. KDJ金叉择时: J < j_buy_threshold 时 K上穿D（超卖区金叉）
  3. 量能确认: 当日成交量 > M日均量（放量）

卖出条件（分仓, 任一触发）:
  - KDJ高位死叉: J > j_sell_threshold 且 K下穿D → 卖半仓
  - BBI跌破: 连续N天收盘价 < BBI → 清仓
  - 追踪止盈: 从持仓最高点回落 > ATR × atr_trail_mult → 清仓
  - 硬止损: 亏损超过 stop_loss_pct → 清仓

指标说明: KDJ/ATR 因参数 (period) 可变，保留内联实现；
BBI 公式固定 (3,6,12,24)，复用 ``quant.data.indicators.BBI`` 的官方实现。
"""
from __future__ import annotations

import pandas as pd

from quant.core.bar import Bar
from quant.core.events import SignalEvent
from quant.core.order import OrderSide
from quant.data.indicators import compute
from quant.strategy.base import Context, Strategy


def _calc_kdj_series(bars: list[Bar], period: int = 9) -> list[tuple[float, float, float]]:
    """返回每根bar的 (K, D, J)，前 period-1 根返回 (50,50,50)。

    与 ``quant.data.indicators.KDJ`` 公式完全一致；此处保留是为了支持
    ``period != 9`` 的策略参数化。
    """
    results: list[tuple[float, float, float]] = []
    k, d = 50.0, 50.0
    for i in range(len(bars)):
        if i < period - 1:
            results.append((50.0, 50.0, 50.0))
            continue
        window = bars[i - period + 1: i + 1]
        lowest = min(b.low for b in window)
        highest = max(b.high for b in window)
        rsv = (bars[i].close - lowest) / (highest - lowest) * 100 if highest != lowest else 50.0
        k = 2.0 / 3.0 * k + 1.0 / 3.0 * rsv
        d = 2.0 / 3.0 * d + 1.0 / 3.0 * k
        j = 3.0 * k - 2.0 * d
        results.append((k, d, j))
    return results


def _calc_bbi_series(bars: list[Bar]) -> pd.Series:
    """BBI = (MA3+MA6+MA12+MA24)/4 — 调用 ``quant.data.indicators.BBI``。"""
    df = pd.DataFrame({"close": [b.close for b in bars]})
    return compute("BBI", df)["bbi"]


def _calc_bbi(closes: list[float], idx: int) -> float | None:
    if idx < 23 or idx >= len(closes):
        return None
    df = pd.DataFrame({"close": closes[: idx + 1]})
    return float(compute("BBI", df)["bbi"].iat[-1])


def _calc_atr(bars: list[Bar], end: int, period: int = 14) -> float:
    """计算截至 end 位置的 ATR。参数化 period，故保留内联。"""
    start = max(1, end - period + 1)
    trs = []
    for i in range(start, end + 1):
        h, l, pc = bars[i].high, bars[i].low, bars[i - 1].close
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs) if trs else 0.0


class BBIKDJTrendStrategy(Strategy):
    """BBI趋势 + KDJ择时策略。

    Params:
        kdj_period:        KDJ 周期 (默认9)
        j_buy_threshold:   J 值买入阈值, J从此值以下金叉 (默认30)
        j_sell_threshold:  J 值卖出阈值, J在此值以上死叉 (默认80)
        bbi_trend_days:    BBI趋势确认天数 (默认3)
        bbi_break_days:    BBI跌破确认天数 (默认2)
        vol_ma_period:     成交量均线周期 (默认5)
        vol_ratio:         放量倍数阈值 (默认1.0, 即大于均量即可)
        atr_period:        ATR 周期 (默认14)
        atr_trail_mult:    追踪止盈ATR倍数 (默认2.5)
        stop_loss_pct:     硬止损百分比 (默认0.05)
    """

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        self._buy_price: dict[str, float] = {}
        self._highest_since_buy: dict[str, float] = {}
        self._half_sold: dict[str, bool] = {}
        self._bbi_below_count: dict[str, int] = {}

    def _has_position(self, ctx: Context, symbol: str) -> bool:
        positions = ctx.portfolio_snapshot.get("positions", {})
        return symbol in positions and positions[symbol]["qty"] > 0

    def on_bar(self, ctx: Context) -> list[SignalEvent]:
        kdj_period = self.params.get("kdj_period", 9)
        j_buy = self.params.get("j_buy_threshold", 30)
        j_sell = self.params.get("j_sell_threshold", 80)
        bbi_trend_days = self.params.get("bbi_trend_days", 3)
        bbi_break_days = self.params.get("bbi_break_days", 2)
        vol_ma_period = self.params.get("vol_ma_period", 5)
        vol_ratio = self.params.get("vol_ratio", 1.0)
        atr_period = self.params.get("atr_period", 14)
        atr_trail = self.params.get("atr_trail_mult", 2.5)
        stop_loss_pct = self.params.get("stop_loss_pct", 0.05)

        signals: list[SignalEvent] = []

        for symbol, bar in ctx.bars.items():
            bars = ctx.latest(symbol, 9999)
            n = len(bars)
            min_bars = max(kdj_period + 2, 25, vol_ma_period + 1, atr_period + 1)
            if n < min_bars:
                continue

            closes = [b.close for b in bars]
            idx = n - 1  # 当前 bar 索引

            # ── 计算指标 ──
            kdj_all = _calc_kdj_series(bars, kdj_period)
            k_now, d_now, j_now = kdj_all[idx]
            k_prev, d_prev, j_prev = kdj_all[idx - 1]

            bbi_now = _calc_bbi(closes, idx)
            bbi_prev = _calc_bbi(closes, idx - bbi_trend_days) if idx >= 23 + bbi_trend_days else None

            has_pos = self._has_position(ctx, symbol)

            # ── 有持仓: 检查卖出 ──
            if has_pos:
                buy_price = self._buy_price.get(symbol, bar.close)

                # 更新持仓最高价
                prev_high = self._highest_since_buy.get(symbol, buy_price)
                self._highest_since_buy[symbol] = max(prev_high, bar.high)
                highest = self._highest_since_buy[symbol]

                # 1) 硬止损
                if bar.close <= buy_price * (1 - stop_loss_pct):
                    signals.append(SignalEvent(
                        symbol=symbol, dt=bar.dt,
                        direction=OrderSide.SELL, strength=1.0,
                    ))
                    self._clear_state(symbol)
                    continue

                # 2) 追踪止盈: 从最高点回落超过 ATR × mult
                atr = _calc_atr(bars, idx, atr_period)
                if atr > 0 and highest - bar.close > atr * atr_trail:
                    signals.append(SignalEvent(
                        symbol=symbol, dt=bar.dt,
                        direction=OrderSide.SELL, strength=1.0,
                    ))
                    self._clear_state(symbol)
                    continue

                # 3) BBI 跌破清仓
                if bbi_now is not None:
                    if bar.close < bbi_now:
                        self._bbi_below_count[symbol] = self._bbi_below_count.get(symbol, 0) + 1
                    else:
                        self._bbi_below_count[symbol] = 0

                    if self._bbi_below_count.get(symbol, 0) >= bbi_break_days:
                        signals.append(SignalEvent(
                            symbol=symbol, dt=bar.dt,
                            direction=OrderSide.SELL, strength=1.0,
                        ))
                        self._clear_state(symbol)
                        continue

                # 4) KDJ 高位死叉 → 卖半仓
                half_sold = self._half_sold.get(symbol, False)
                if not half_sold:
                    if (j_now > j_sell
                            and k_prev >= d_prev and k_now < d_now):
                        signals.append(SignalEvent(
                            symbol=symbol, dt=bar.dt,
                            direction=OrderSide.SELL, strength=0.5,
                        ))
                        self._half_sold[symbol] = True

            # ── 无持仓: 检查买入 ──
            else:
                if bbi_now is None or bbi_prev is None:
                    continue

                # 条件1: BBI上升趋势 + 价格在BBI上方
                if bbi_now <= bbi_prev:
                    continue
                if bar.close <= bbi_now:
                    continue

                # 条件2: KDJ金叉 — J从低位, K上穿D
                if j_prev >= j_buy:
                    continue  # 前一天J必须在低位
                if not (k_prev <= d_prev and k_now > d_now):
                    continue  # K上穿D

                # 条件3: 放量确认
                recent_vols = [b.volume for b in bars[idx - vol_ma_period: idx]]
                if not recent_vols:
                    continue
                avg_vol = sum(recent_vols) / len(recent_vols)
                if avg_vol <= 0 or bar.volume < avg_vol * vol_ratio:
                    continue

                # 全部满足 → 买入
                signals.append(SignalEvent(
                    symbol=symbol, dt=bar.dt,
                    direction=OrderSide.BUY, strength=1.0,
                ))
                self._buy_price[symbol] = bar.close
                self._highest_since_buy[symbol] = bar.high
                self._half_sold[symbol] = False
                self._bbi_below_count[symbol] = 0

        return signals

    def _clear_state(self, symbol: str) -> None:
        self._buy_price.pop(symbol, None)
        self._highest_since_buy.pop(symbol, None)
        self._half_sold.pop(symbol, None)
        self._bbi_below_count.pop(symbol, None)
