"""抄底策略 smoke：6 样例选股命中检查 + 3 标的回测。

用法：
    python -m scripts.dip_buy_smoke
or:
    /root/quant/.venv/bin/python /root/quant/scripts/dip_buy_smoke.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 让脚本能从 repo root 直接 python scripts/dip_buy_smoke.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quant.data import get_store
from server.models.backtest import BacktestRequest
from server.models.screening import ScreenRequest
from server.services.backtest_service import run_backtest
from server.services.screening_service import run_screening


# doc 标记的 6 个 2025 年「完美图形买点」
SAMPLES: list[tuple[str, str, str]] = [
    ("华纳药厂", "688799", "2025-05-08"),
    ("方正科技", "600601", "2025-07-16"),
    ("中科金财", "002657", "2025-08-04"),
    ("宁波韵升", "600366", "2025-08-05"),
    ("瑞达期货", "002961", "2025-11-06"),
    ("航天发展", "000547", "2025-11-12"),
]


def precheck_data() -> None:
    """前置数据校验：parquet 已含到目标日期。"""
    store = get_store()
    missing: list[str] = []
    for name, sym, dt in SAMPLES:
        df = store.get_kline(sym, freq="day", end=dt)
        if df is None or df.empty:
            missing.append(f"{name}({sym}) 缺数据")
            continue
        last_dt = str(df["dt"].max())
        if last_dt < dt:
            missing.append(f"{name}({sym}) 数据只到 {last_dt}，缺 {dt}")
    if missing:
        print("⚠️  数据覆盖不全：")
        for m in missing:
            print(f"  - {m}")
        print("先跑 update_universe(workers=8) 补数据，再回头跑本脚本。")
        sys.exit(1)
    print("✅ 数据覆盖检查通过\n")


def run_screening_samples() -> int:
    """对每个样例日期跑全 A 选股，看样本 symbol 是否在 matches 里。"""
    print("─── 选股命中检查 ───")
    hits = 0
    for name, sym, dt in SAMPLES:
        r = run_screening(ScreenRequest(strategy="dip_buy", scan_date=dt, lookback=120))
        hit = any(m.symbol == sym for m in r.matches)
        marker = "✓" if hit else "✗"
        print(f"  {marker} {dt} {name}({sym}): hit={hit}, "
              f"total_matches={len(r.matches)}, elapsed={r.elapsed_seconds}s")
        hits += hit
    print(f"\n命中率：{hits}/{len(SAMPLES)}")
    return hits


def run_backtest_smoke() -> None:
    """三个样例标的合并回测一段。"""
    print("\n─── 回测 smoke ───")
    res = run_backtest(BacktestRequest(
        strategy="dip_buy",
        symbols=["688799", "002657", "002961"],
        start_date="2024-06-01",
        end_date="2025-12-15",
        initial_cash=1_000_000,
        max_position_pct=0.3,
        max_drawdown=0.2,
        commission_rate=0.00025,
        strategy_params={},
    ))
    m = res.metrics
    print(f"  trades={m.trade_count}, total_return={m.total_return:.2%}, "
          f"annual_return={m.annual_return:.2%}, max_drawdown={m.max_drawdown:.2%}")
    print(f"  win_rate={m.win_rate}, sharpe={m.sharpe_ratio}, pl_ratio={m.profit_loss_ratio}")
    print(f"  equity_curve_len={len(res.equity_curve)}")


def main() -> None:
    precheck_data()
    run_screening_samples()
    run_backtest_smoke()


if __name__ == "__main__":
    main()
