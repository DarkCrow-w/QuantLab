from __future__ import annotations

from quant.data.akshare_feed import AKShareFeed
from server.models.backtest import KlineBar


def get_kline(symbol: str, start_date: str, end_date: str) -> list[KlineBar]:
    feed = AKShareFeed(start_date=start_date, end_date=end_date, use_cache=True)
    feed.subscribe([symbol])
    df = feed._data.get(symbol)
    if df is None or df.empty:
        return []
    bars = []
    for _, r in df.iterrows():
        bars.append(KlineBar(
            dt=str(r["dt"]),
            open=round(float(r["open"]), 4),
            high=round(float(r["high"]), 4),
            low=round(float(r["low"]), 4),
            close=round(float(r["close"]), 4),
            volume=float(r["volume"]),
        ))
    return bars
