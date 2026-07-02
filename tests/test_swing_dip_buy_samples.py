from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from quant.core.bar import Bar
from quant.strategy.examples.dip_buy import SwingDipBuyStrategy, _bars_to_df


ROOT = Path(__file__).resolve().parents[1]

SAMPLE_BUY_DATES = {
    "600601": ["2025-07-16", "2025-07-23"],
    "688799": ["2025-05-07", "2025-05-08", "2025-05-09"],
    "600366": ["2025-08-01"],
    "301076": ["2025-08-01"],
    "002657": ["2025-08-05"],
}


def _load_bars(symbol: str) -> list[Bar]:
    path = ROOT / "data" / "market" / "day" / f"{symbol}.parquet"
    if not path.exists():
        pytest.skip(f"sample market data missing: {path}")
    frame = pd.read_parquet(path)
    frame["dt"] = pd.to_datetime(frame["dt"]).dt.strftime("%Y-%m-%d")
    return [
        Bar(
            dt=row.dt,
            symbol=symbol,
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=float(row.volume),
            amount=float(getattr(row, "amount", 0)),
        )
        for row in frame.itertuples(index=False)
    ]


def _score(strategy: SwingDipBuyStrategy, bars: list[Bar]) -> int:
    params = strategy.params
    score, _ = strategy._entry_score(
        bars,
        _bars_to_df(bars),
        lookback=params.get("lookback", 30),
        kdj_j_threshold=params.get("kdj_j_threshold", 18),
        rsi3_threshold=params.get("rsi3_threshold", 28),
        rsi6_threshold=params.get("rsi6_threshold", 32),
        bbi_lower_band_pct=params.get("bbi_lower_band_pct", 0.10),
        bbi_upper_band_pct=params.get("bbi_upper_band_pct", 0.03),
        panic_volume_ratio=params.get("panic_volume_ratio", 1.8),
        dryup_ratio=params.get("dryup_ratio", 0.85),
        reversal_pct=params.get("reversal_pct", 0.003),
        trend_floor_pct=params.get("trend_floor_pct", 0.08),
        attack_lookback=params.get("attack_lookback", 40),
        attack_gain_pct=params.get("attack_gain_pct", 2.5),
        attack_volume_ratio=params.get("attack_volume_ratio", 1.8),
        attack_volume_ma_period=params.get("attack_volume_ma_period", 20),
        calm_pct_chg=params.get("calm_pct_chg", 3.0),
        calm_amp_pct=params.get("calm_amp_pct", 5.0),
        low_support_lookback=params.get("low_support_lookback", 20),
        low_support_buffer_pct=params.get("low_support_buffer_pct", 0.0),
    )
    return score


def test_swing_dip_buy_covers_volume_attack_pullback_samples():
    strategy = SwingDipBuyStrategy({})
    entry_score = strategy.params.get("entry_score", 9)

    for symbol, dates in SAMPLE_BUY_DATES.items():
        bars = _load_bars(symbol)
        by_date = {str(bar.dt): index for index, bar in enumerate(bars)}
        for date in dates:
            assert date in by_date
            score = _score(strategy, bars[: by_date[date] + 1])
            assert score >= entry_score, f"{symbol} {date} scored {score}"
