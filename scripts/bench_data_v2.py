#!/usr/bin/env python3
"""数据层 v2 性能基准。

测量：
1. 单只 K 线读取（含/不含指标重算）
2. 批量读取（100 只）
3. 全市场扫描（截面查询）
4. update_universe 模拟（mock source，去掉网络）

用法： python scripts/bench_data_v2.py
"""
from __future__ import annotations

import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quant.data import OHLCV_COLUMNS, compute_all, get_store, update_universe  # noqa: E402


def _hr(name: str) -> None:
    print(f"\n── {name} ──")


def bench_single_read() -> None:
    _hr("单只读取（含 24 指标列）")
    store = get_store()
    syms = store.list_symbols("day")[:5]
    if not syms:
        print("  no data — skipped")
        return
    times = []
    for sym in syms:
        t0 = time.perf_counter()
        df = store.get_kline(sym, freq="day")
        times.append(time.perf_counter() - t0)
    print(f"  symbols sampled: {len(syms)}")
    print(f"  rows per file:   {len(df) if syms else 0}")
    print(f"  avg latency:     {np.mean(times) * 1000:.2f} ms")
    print(f"  p95 latency:     {np.percentile(times, 95) * 1000:.2f} ms")


def bench_batch_read() -> None:
    _hr("批量读取 100 只")
    store = get_store()
    syms = store.list_symbols("day")[:100]
    if len(syms) < 100:
        print(f"  only {len(syms)} symbols — skipped")
        return
    t0 = time.perf_counter()
    dfs = store.get_klines(syms, freq="day", columns=OHLCV_COLUMNS)
    elapsed = time.perf_counter() - t0
    total_rows = sum(len(df) for df in dfs.values())
    print(f"  symbols:    {len(syms)}")
    print(f"  total rows: {total_rows:,}")
    print(f"  elapsed:    {elapsed:.2f} s ({total_rows / elapsed:,.0f} rows/s)")


def bench_cross_section() -> None:
    _hr("全市场截面（5,205 只 × 最新 1 行）")
    store = get_store()
    syms = store.list_symbols("day")
    if not syms:
        print("  no data — skipped")
        return
    t0 = time.perf_counter()
    df = store.get_latest_snapshot(
        syms,
        freq="day",
        columns=["dt", "close", "macd", "kdj_j", "bbi"],
    )
    elapsed = time.perf_counter() - t0
    print(f"  symbols scanned: {len(syms)}")
    print(f"  rows assembled:  {len(df)}")
    print(f"  elapsed:         {elapsed:.2f} s ({len(syms) / elapsed:,.0f} sym/s)")
    if not df.empty:
        print(f"  example: 600519 close = {df[df['symbol'] == '600519']['close'].iloc[0]:.2f}")


def bench_indicator_recompute() -> None:
    _hr("指标全量重算（500 只 × 20 指标）")
    store = get_store()
    syms = store.list_symbols("day")[:500]
    if len(syms) < 100:
        print(f"  only {len(syms)} — skipped")
        return
    t0 = time.perf_counter()
    n_rows = 0
    for sym in syms:
        df = store.get_kline(sym, freq="day", columns=OHLCV_COLUMNS)
        if df.empty:
            continue
        out = compute_all(df)
        n_rows += len(out)
    elapsed = time.perf_counter() - t0
    print(f"  symbols:  {len(syms)}")
    print(f"  rows:     {n_rows:,}")
    print(f"  elapsed:  {elapsed:.2f} s ({n_rows / elapsed:,.0f} rows/s)")


class _MockSource:
    name = "bench_mock"

    def __init__(self, n_bars: int) -> None:
        self.n_bars = n_bars

    def fetch_daily(self, symbol, start, end):
        rng = np.random.default_rng(hash(symbol) & 0xFFFF)
        dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(self.n_bars)]
        close = 100 + np.cumsum(rng.normal(0, 1, self.n_bars))
        return pd.DataFrame({
            "dt": dates, "open": close, "high": close + 1,
            "low": close - 1, "close": close,
            "volume": rng.integers(1e6, 5e6, self.n_bars).astype(float),
            "amount": rng.integers(1e8, 5e8, self.n_bars).astype(float),
        })

    def list_symbols(self): return []


def bench_update_universe_mock(
    workers: int = 4,
    recompute_indicators: bool = False,
) -> None:
    mode = "eager indicators" if recompute_indicators else "deferred indicators"
    _hr(f"update_universe 并发 (mock source, workers={workers}, {mode})")
    import tempfile

    from quant.data import DataStore
    with tempfile.TemporaryDirectory() as td:
        store = DataStore(root=Path(td))
        symbols = [f"{600000 + i:06d}" for i in range(100)]
        src = _MockSource(n_bars=500)
        t0 = time.perf_counter()
        report = update_universe(
            symbols=symbols, sources=[src], workers=workers,
            end_date=date(2024, 6, 1), store=store,
            recompute_indicators=recompute_indicators,
        )
        elapsed = time.perf_counter() - t0
        print(f"  symbols:  {report.total}")
        print(f"  updated:  {report.updated}, failed: {report.failed}")
        print(f"  elapsed:  {elapsed:.2f} s ({report.total / elapsed:,.0f} sym/s)")
        print(f"  rows/s:   {report.total * 500 / elapsed:,.0f}")


def main() -> None:
    print("Quant Data Layer v2 — Benchmark")
    print(f"Date: {date.today()}")
    bench_single_read()
    bench_batch_read()
    bench_indicator_recompute()
    bench_update_universe_mock(workers=4, recompute_indicators=False)
    bench_cross_section()


if __name__ == "__main__":
    main()
