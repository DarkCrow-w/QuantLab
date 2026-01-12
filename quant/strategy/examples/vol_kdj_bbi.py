"""
量价 + KDJ + BBI 策略

买入条件（全部满足）:
  1. N型结构上升: MA上升趋势 + 近期回踩不破前低（higher low）
  2. 量价配合: 涨日均量/跌日均量 >= vol_ratio (默认1.5)
  3. KDJ 的 J 值 < 阈值（默认10，越低越好）

卖出条件（分仓）:
  - 盈利后连续2天站上BBI → 卖一半
  - 剩余仓位连续2天跌破BBI → 清仓

止损:
  - 固定百分比: 买入价 × (1 - stop_loss_pct)
  - 或 ATR动态: 买入价 - ATR × atr_multiplier
"""
from __future__ import annotations

from quant.core.bar import Bar
from quant.core.events import SignalEvent
from quant.core.order import OrderSide
from quant.strategy.base import Context, Strategy


def _calc_kdj(bars: list[Bar], period: int = 9) -> tuple[float, float, float]:
    """计算最新一根K线的 KDJ 值。"""
    if len(bars) < period:
        return 50.0, 50.0, 50.0

    k, d = 50.0, 50.0
    for i in range(period - 1, len(bars)):
        window = bars[i - period + 1: i + 1]
        lowest = min(b.low for b in window)
        highest = max(b.high for b in window)
        if highest == lowest:
            rsv = 50.0
        else:
            rsv = (bars[i].close - lowest) / (highest - lowest) * 100
        k = 2.0 / 3.0 * k + 1.0 / 3.0 * rsv
        d = 2.0 / 3.0 * d + 1.0 / 3.0 * k
    j = 3.0 * k - 2.0 * d
    return k, d, j


def _calc_bbi(closes: list[float]) -> float | None:
    """BBI = (MA3 + MA6 + MA12 + MA24) / 4"""
    if len(closes) < 24:
        return None
    periods = [3, 6, 12, 24]
    total = 0.0
    for p in periods:
        total += sum(closes[-p:]) / p
    return total / 4.0


def _calc_atr(bars: list[Bar], period: int = 14) -> float:
    """Average True Range."""
    if len(bars) < 2:
        return 0.0
    trs: list[float] = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i].high, bars[i].low, bars[i - 1].close
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return sum(trs) / len(trs) if trs else 0.0
    return sum(trs[-period:]) / period


class VolKDJBBIStrategy(Strategy):
    """量价KDJ买入 + BBI分仓卖出策略。

    Params:
        ma_period:       均线周期, 用于判断N型上升 (默认20)
        vol_lookback:    量能观察窗口 (默认20)
        vol_ratio:       涨日均量/跌日均量 倍数阈值 (默认1.5)
        kdj_period:      KDJ 计算周期 (默认9)
        j_threshold:     J 值买入阈值 (默认10)
        bbi_confirm_days:BBI 确认天数 (默认2)
        stop_loss_pct:   固定止损百分比 (默认0.05)
        atr_period:      ATR 周期 (默认14)
        atr_multiplier:  ATR 止损倍数 (默认2.0)
        stop_mode:       止损模式 "fixed" 或 "atr" (默认 "fixed")
    """

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        # 持仓状态追踪
        self._buy_price: dict[str, float] = {}
        self._stop_price: dict[str, float] = {}
        self._half_sold: dict[str, bool] = {}
        self._bbi_above_count: dict[str, int] = {}
        self._bbi_below_count: dict[str, int] = {}

    def _has_position(self, ctx: Context, symbol: str) -> bool:
        positions = ctx.portfolio_snapshot.get("positions", {})
        return symbol in positions and positions[symbol]["qty"] > 0

    def _check_n_shape(self, bars: list[Bar], ma_period: int) -> bool:
        """N型结构: MA上升 + higher low（近期低点高于更早的低点）。"""
        if len(bars) < ma_period + 5:
            return False
        closes = [b.close for b in bars]

        # MA 上升趋势
        ma_now = sum(closes[-ma_period:]) / ma_period
        ma_prev = sum(closes[-ma_period - 5:-5]) / ma_period
        if ma_now <= ma_prev:
            return False

        # 价格在 MA 之上
        if closes[-1] < ma_now:
            return False

        # higher low: 近半段最低 > 远半段最低
        half = ma_period // 2
        recent_low = min(b.low for b in bars[-half:])
        earlier_low = min(b.low for b in bars[-ma_period:-half])
        return recent_low > earlier_low

    def _check_volume_pattern(self, bars: list[Bar], lookback: int,
                               vol_ratio: float) -> bool:
        """放量涨、缩量跌: 上涨日均量 / 下跌日均量 > vol_ratio。"""
        if len(bars) < lookback:
            return False
        window = bars[-lookback:]

        up_vols = [b.volume for b in window if b.close > b.open]
        down_vols = [b.volume for b in window if b.close < b.open]

        if not up_vols or not down_vols:
            return False

        avg_up = sum(up_vols) / len(up_vols)
        avg_down = sum(down_vols) / len(down_vols)

        return avg_down > 0 and avg_up / avg_down >= vol_ratio

    def on_bar(self, ctx: Context) -> list[SignalEvent]:
        ma_period = self.params.get("ma_period", 20)
        vol_lookback = self.params.get("vol_lookback", 20)
        vol_ratio = self.params.get("vol_ratio", 1.5)
        kdj_period = self.params.get("kdj_period", 9)
        j_threshold = self.params.get("j_threshold", 10)
        bbi_confirm = self.params.get("bbi_confirm_days", 2)
        stop_loss_pct = self.params.get("stop_loss_pct", 0.05)
        atr_period = self.params.get("atr_period", 14)
        atr_mult = self.params.get("atr_multiplier", 2.0)
        stop_mode = self.params.get("stop_mode", "fixed")

        signals: list[SignalEvent] = []

        for symbol, bar in ctx.bars.items():
            bars = ctx.latest(symbol, 9999)
            closes = [b.close for b in bars]
            has_pos = self._has_position(ctx, symbol)

            # ── 有持仓: 检查卖出条件 ──
            if has_pos:
                buy_price = self._buy_price.get(symbol, bar.close)
                stop_price = self._stop_price.get(symbol, 0)
                half_sold = self._half_sold.get(symbol, False)

                # 1) 止损检查
                if bar.close <= stop_price:
                    signals.append(SignalEvent(
                        symbol=symbol, dt=bar.dt,
                        direction=OrderSide.SELL, strength=1.0,
                    ))
                    self._clear_state(symbol)
                    continue

                # 2) BBI 卖出逻辑
                bbi = _calc_bbi(closes)
                if bbi is None:
                    continue

                if bar.close > bbi:
                    self._bbi_above_count[symbol] = self._bbi_above_count.get(symbol, 0) + 1
                    self._bbi_below_count[symbol] = 0
                else:
                    self._bbi_below_count[symbol] = self._bbi_below_count.get(symbol, 0) + 1
                    self._bbi_above_count[symbol] = 0

                if not half_sold:
                    # 盈利 + 连续N天站上BBI → 卖一半
                    if (bar.close > buy_price
                            and self._bbi_above_count.get(symbol, 0) >= bbi_confirm):
                        signals.append(SignalEvent(
                            symbol=symbol, dt=bar.dt,
                            direction=OrderSide.SELL, strength=0.5,
                        ))
                        self._half_sold[symbol] = True
                else:
                    # 已卖半仓, 连续N天跌破BBI → 清仓
                    if self._bbi_below_count.get(symbol, 0) >= bbi_confirm:
                        signals.append(SignalEvent(
                            symbol=symbol, dt=bar.dt,
                            direction=OrderSide.SELL, strength=1.0,
                        ))
                        self._clear_state(symbol)

            # ── 无持仓: 检查买入条件 ──
            else:
                if len(bars) < max(ma_period + 5, vol_lookback, kdj_period, 24):
                    continue

                # 条件1: N型结构
                if not self._check_n_shape(bars, ma_period):
                    continue

                # 条件2: 量价配合
                if not self._check_volume_pattern(bars, vol_lookback, vol_ratio):
                    continue

                # 条件3: KDJ J < 阈值
                _k, _d, j = _calc_kdj(bars, kdj_period)
                if j >= j_threshold:
                    continue

                # 全部满足 → 买入
                signals.append(SignalEvent(
                    symbol=symbol, dt=bar.dt,
                    direction=OrderSide.BUY, strength=1.0,
                ))
                # 记录买入状态（下一根 bar 成交后用 open 价更准确,
                # 这里先用 close 近似, 足够计算止损参考）
                self._buy_price[symbol] = bar.close
                self._half_sold[symbol] = False
                self._bbi_above_count[symbol] = 0
                self._bbi_below_count[symbol] = 0

                # 计算止损价
                if stop_mode == "atr":
                    atr = _calc_atr(bars, atr_period)
                    self._stop_price[symbol] = bar.close - atr * atr_mult
                else:
                    self._stop_price[symbol] = bar.close * (1 - stop_loss_pct)

        return signals

    def _clear_state(self, symbol: str) -> None:
        self._buy_price.pop(symbol, None)
        self._stop_price.pop(symbol, None)
        self._half_sold.pop(symbol, None)
        self._bbi_above_count.pop(symbol, None)
        self._bbi_below_count.pop(symbol, None)
