from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from server.models.backtest import KlineBar, TradeRecord
from server.services.factor_strategy_service import FactorStrategyStore
from server.services.market_service import get_kline

VOLUME_PULLBACK_STRATEGY_ID = "preset_volume_pullback_swing_dip"
LEGACY_SWING_DIP_ALIAS = "swing_dip_buy"


@dataclass(frozen=True)
class StrategySampleSeed:
    id: str
    strategy: str
    symbol: str
    name: str
    observation_start: str
    observation_end: str
    buy_dates: tuple[str, ...]
    reduce_date: str | None
    exit_date: str | None
    reason: str
    stop_loss_date: str | None = None
    holding: bool = False
    required: bool = True


SAMPLE_SEEDS: tuple[StrategySampleSeed, ...] = (
    StrategySampleSeed(
        id="swing-dip-600601-202507",
        strategy=VOLUME_PULLBACK_STRATEGY_ID,
        symbol="600601",
        name="方正科技",
        observation_start="2025-06-05",
        observation_end="2025-09-26",
        buy_dates=("2025-07-16", "2025-07-23"),
        reduce_date="2025-07-29",
        exit_date="2025-09-29",
        reason="放量上涨后缩量下跌，回调不破60日趋势区，KDJ-J低位且未跌破区间低位。",
    ),
    StrategySampleSeed(
        id="swing-dip-688799-202505",
        strategy=VOLUME_PULLBACK_STRATEGY_ID,
        symbol="688799",
        name="华纳药厂",
        observation_start="2025-04-08",
        observation_end="2025-06-18",
        buy_dates=("2025-05-07", "2025-05-08", "2025-05-09"),
        reduce_date="2025-05-21",
        exit_date="2025-06-18",
        reason="放量上涨后连续缩量回调，KDJ-J低位，趋势结构未破。",
    ),
    StrategySampleSeed(
        id="swing-dip-600366-202508",
        strategy=VOLUME_PULLBACK_STRATEGY_ID,
        symbol="600366",
        name="宁波韵升",
        observation_start="2025-06-05",
        observation_end="2025-09-03",
        buy_dates=("2025-08-01",),
        reduce_date="2025-08-11",
        exit_date="2025-09-03",
        reason="放量上涨后缩量回调，RSI(3)低于20，未跌破区间低位。",
    ),
    StrategySampleSeed(
        id="swing-dip-301076-202508",
        strategy=VOLUME_PULLBACK_STRATEGY_ID,
        symbol="301076",
        name="新瀚新材",
        observation_start="2025-07-10",
        observation_end="2025-08-27",
        buy_dates=("2025-08-01",),
        reduce_date="2025-08-07",
        exit_date="2025-08-27",
        reason="放量上涨后缩量回调，KDJ-J低位，低点结构保持完整。",
    ),
    StrategySampleSeed(
        id="swing-dip-002657-202508",
        strategy=VOLUME_PULLBACK_STRATEGY_ID,
        symbol="002657",
        name="中科金财",
        observation_start="2025-05-29",
        observation_end="2025-09-03",
        buy_dates=("2025-08-05",),
        reduce_date="2025-08-15",
        exit_date="2025-09-03",
        reason="放量上涨后缩量回调，KDJ-J低位，回踩未破近端低位。",
    ),
    StrategySampleSeed(
        id="swing-dip-000776-202505",
        strategy=VOLUME_PULLBACK_STRATEGY_ID,
        symbol="000776",
        name="广发证券",
        observation_start="2025-05-28",
        observation_end="2025-09-03",
        buy_dates=("2025-05-28",),
        reduce_date="2025-07-10",
        exit_date="2025-09-03",
        reason="放量上涨后的缩量回调买点，后续按连续上涨减仓、跌破趋势清仓处理。",
    ),
    StrategySampleSeed(
        id="swing-dip-605098-202605",
        strategy=VOLUME_PULLBACK_STRATEGY_ID,
        symbol="605098",
        name="行动教育",
        observation_start="2026-05-20",
        observation_end="2026-05-22",
        buy_dates=("2026-05-20",),
        reduce_date=None,
        exit_date=None,
        stop_loss_date="2026-05-22",
        reason="买入后未延续修复，触发止损退出。",
    ),
    StrategySampleSeed(
        id="swing-dip-301345-202605",
        strategy=VOLUME_PULLBACK_STRATEGY_ID,
        symbol="301345",
        name="涛涛车业",
        observation_start="2026-05-13",
        observation_end="2026-05-14",
        buy_dates=("2026-05-13",),
        reduce_date=None,
        exit_date=None,
        stop_loss_date="2026-05-14",
        reason="买入次日未守住回调支撑，按止损样例记录。",
    ),
    StrategySampleSeed(
        id="swing-dip-002127-202605",
        strategy=VOLUME_PULLBACK_STRATEGY_ID,
        symbol="002127",
        name="南极电商",
        observation_start="2026-05-26",
        observation_end="2026-05-29",
        buy_dates=("2026-05-26",),
        reduce_date=None,
        exit_date=None,
        stop_loss_date="2026-05-29",
        reason="买入后回踩失败，按止损样例记录。",
    ),
    StrategySampleSeed(
        id="swing-dip-603130-202605",
        strategy=VOLUME_PULLBACK_STRATEGY_ID,
        symbol="603130",
        name="云中马",
        observation_start="2026-05-20",
        observation_end="2026-05-27",
        buy_dates=("2026-05-20",),
        reduce_date=None,
        exit_date=None,
        stop_loss_date="2026-05-27",
        reason="买入后未形成有效反弹，触发止损退出。",
    ),
    StrategySampleSeed(
        id="swing-dip-600763-202603",
        strategy=VOLUME_PULLBACK_STRATEGY_ID,
        symbol="600763",
        name="通策医疗",
        observation_start="2026-03-09",
        observation_end="2026-03-12",
        buy_dates=("2026-03-09",),
        reduce_date=None,
        exit_date=None,
        stop_loss_date="2026-03-12",
        reason="买入后短期走弱，触发止损退出。",
    ),
    StrategySampleSeed(
        id="swing-dip-300868-202604",
        strategy=VOLUME_PULLBACK_STRATEGY_ID,
        symbol="300868",
        name="杰美特",
        observation_start="2026-04-28",
        observation_end="2026-06-11",
        buy_dates=("2026-04-28",),
        reduce_date="2026-05-08",
        exit_date="2026-06-11",
        reason="放量后缩量回踩买入，随后减仓并在趋势转弱时清仓。",
    ),
    StrategySampleSeed(
        id="swing-dip-301200-202604",
        strategy=VOLUME_PULLBACK_STRATEGY_ID,
        symbol="301200",
        name="大族数控",
        observation_start="2026-04-29",
        observation_end="2026-06-11",
        buy_dates=("2026-04-29",),
        reduce_date="2026-05-12",
        exit_date="2026-06-11",
        reason="放量上涨后的缩量回调买点，后续按策略减仓、清仓。",
    ),
    StrategySampleSeed(
        id="swing-dip-301200-202606",
        strategy=VOLUME_PULLBACK_STRATEGY_ID,
        symbol="301200",
        name="大族数控",
        observation_start="2026-06-11",
        observation_end="2026-07-02",
        buy_dates=("2026-06-11",),
        reduce_date="2026-06-15",
        exit_date=None,
        reason="二次买入后已减仓，剩余仓位仍按趋势持有中。",
        holding=True,
    ),
)


def list_strategy_samples(strategy: str | None = None) -> dict[str, Any]:
    selected_strategy = _normalize_strategy_id(strategy)
    seeds = [
        seed for seed in SAMPLE_SEEDS
        if selected_strategy is None or seed.strategy == selected_strategy
    ]
    samples = [_build_sample(seed) for seed in seeds]
    trades = [
        {
            **trade,
            "sample_id": sample["id"],
            "strategy": sample["strategy"],
            "reason": sample["reason"],
            "observation_start": sample["observation_start"],
            "observation_end": sample["observation_end"],
            "kline": sample["kline"],
            "chart_trades": sample["chart_trades"],
        }
        for sample in samples
        for trade in sample["trades"]
    ]
    winning = [trade for trade in trades if trade.get("total_return_pct", 0) > 0]
    avg_return = (
        round(sum(trade.get("total_return_pct", 0) for trade in trades) / len(trades), 2)
        if trades else 0.0
    )
    return {
        "strategy": selected_strategy or "all",
        "strategies": _strategy_options(),
        "summary": {
            "sample_count": len(samples),
            "trade_count": len(trades),
            "win_count": len(winning),
            "win_rate": round(len(winning) / len(trades), 4) if trades else 0.0,
            "avg_return_pct": avg_return,
            "best_return_pct": max((trade.get("total_return_pct", 0) for trade in trades), default=0.0),
            "worst_return_pct": min((trade.get("total_return_pct", 0) for trade in trades), default=0.0),
        },
        "samples": samples,
        "trades": trades,
    }


def _normalize_strategy_id(strategy: str | None) -> str | None:
    if strategy == LEGACY_SWING_DIP_ALIAS:
        return VOLUME_PULLBACK_STRATEGY_ID
    return strategy


def _strategy_options() -> list[dict[str, Any]]:
    sample_counts: dict[str, dict[str, int]] = {}
    for seed in SAMPLE_SEEDS:
        counts = sample_counts.setdefault(seed.strategy, {"sample_count": 0, "trade_count": 0})
        counts["sample_count"] += 1
        counts["trade_count"] += len(seed.buy_dates)

    seen: set[str] = set()
    options: list[dict[str, Any]] = []
    for strategy in FactorStrategyStore().list():
        counts = sample_counts.get(strategy.id, {"sample_count": 0, "trade_count": 0})
        options.append({
            "id": strategy.id,
            "name": strategy.id,
            "display_name": strategy.name,
            "description": strategy.description,
            "sample_count": counts["sample_count"],
            "trade_count": counts["trade_count"],
            "has_samples": counts["sample_count"] > 0,
        })
        seen.add(strategy.id)

    for strategy_id, counts in sample_counts.items():
        if strategy_id in seen:
            continue
        options.append({
            "id": strategy_id,
            "name": strategy_id,
            "display_name": strategy_id,
            "description": "",
            "sample_count": counts["sample_count"],
            "trade_count": counts["trade_count"],
            "has_samples": True,
        })
    return options


def _build_sample(seed: StrategySampleSeed) -> dict[str, Any]:
    end_date = _sample_end_date(seed)
    kline = get_kline(seed.symbol, seed.observation_start, end_date)
    prices = {bar.dt: bar.close for bar in kline}
    trades = [
        _build_trade(seed, index=index, buy_date=buy_date, prices=prices)
        for index, buy_date in enumerate(seed.buy_dates, start=1)
    ]
    return {
        "id": seed.id,
        "strategy": seed.strategy,
        "symbol": seed.symbol,
        "name": seed.name,
        "observation_start": seed.observation_start,
        "observation_end": seed.observation_end,
        "buy_dates": list(seed.buy_dates),
        "reduce_date": seed.reduce_date,
        "exit_date": seed.exit_date,
        "stop_loss_date": seed.stop_loss_date,
        "holding": seed.holding,
        "reason": seed.reason,
        "required": seed.required,
        "trades": trades,
        "kline": [bar.model_dump() for bar in kline],
        "chart_trades": _chart_trades(seed, prices),
    }


def _build_trade(
    seed: StrategySampleSeed,
    *,
    index: int,
    buy_date: str,
    prices: dict[str, float],
) -> dict[str, Any]:
    buy_price = prices.get(buy_date)
    reduce_price = prices.get(seed.reduce_date) if seed.reduce_date else None
    stop_loss_price = prices.get(seed.stop_loss_date) if seed.stop_loss_date else None
    exit_price = prices.get(seed.exit_date) if seed.exit_date else None
    mark_price = prices.get(seed.observation_end) if seed.holding else None
    mark_date = seed.observation_end
    if seed.holding and mark_price is None:
        latest_mark = _latest_price(prices, seed.observation_end)
        if latest_mark is not None:
            mark_date, mark_price = latest_mark
    final_date = seed.stop_loss_date or seed.exit_date or seed.observation_end
    if seed.holding:
        final_date = mark_date
    final_price = stop_loss_price or exit_price or mark_price
    if buy_price is None or final_price is None:
        return {
            "id": f"{seed.id}-{index}",
            "symbol": seed.symbol,
            "name": seed.name,
            "buy_date": buy_date,
            "reduce_date": seed.reduce_date or "",
            "exit_date": final_date,
            "stop_loss_date": seed.stop_loss_date,
            "trade_status": _trade_status(seed),
            "status": "missing_price",
            "message": "样例日期缺少本地K线价格",
        }

    reduce_return = (reduce_price / buy_price - 1) if reduce_price else None
    final_return = final_price / buy_price - 1
    total_return = (
        ((reduce_return or 0) + final_return) / 2
        if reduce_price else final_return
    )
    return {
        "id": f"{seed.id}-{index}",
        "symbol": seed.symbol,
        "name": seed.name,
        "buy_date": buy_date,
        "reduce_date": seed.reduce_date or "",
        "exit_date": final_date,
        "stop_loss_date": seed.stop_loss_date,
        "trade_status": _trade_status(seed),
        "buy_price": round(buy_price, 3),
        "reduce_price": round(reduce_price, 3) if reduce_price else None,
        "exit_price": round(final_price, 3),
        "reduce_return_pct": round(reduce_return * 100, 2) if reduce_return is not None else None,
        "exit_return_pct": round(final_return * 100, 2),
        "total_return_pct": round(total_return * 100, 2),
        "holding_days": _days_between(buy_date, final_date),
        "status": "completed",
        "message": "",
    }


def _chart_trades(seed: StrategySampleSeed, prices: dict[str, float]) -> list[dict[str, Any]]:
    trades: list[TradeRecord] = []
    qty = 1000
    for buy_date in seed.buy_dates:
        buy_price = prices.get(buy_date)
        if buy_price is None:
            continue
        trades.append(TradeRecord(
            dt=buy_date,
            symbol=seed.symbol,
            side="BUY",
            qty=qty,
            price=buy_price,
            commission=0,
        ))
        reduce_price = prices.get(seed.reduce_date) if seed.reduce_date else None
        if reduce_price is not None and seed.reduce_date:
            trades.append(TradeRecord(
                dt=seed.reduce_date,
                symbol=seed.symbol,
                side="SELL",
                qty=qty // 2,
                price=reduce_price,
                commission=0,
            ))
        final_date = seed.stop_loss_date or seed.exit_date
        exit_price = prices.get(final_date) if final_date else None
        if exit_price is not None and final_date:
            trades.append(TradeRecord(
                dt=final_date,
                symbol=seed.symbol,
                side="SELL",
                qty=qty if seed.stop_loss_date or not seed.reduce_date else qty // 2,
                price=exit_price,
                commission=0,
            ))
    return [trade.model_dump() for trade in trades]


def _sample_end_date(seed: StrategySampleSeed) -> str:
    return seed.stop_loss_date or seed.exit_date or seed.observation_end


def _trade_status(seed: StrategySampleSeed) -> str:
    if seed.stop_loss_date:
        return "stop_loss"
    if seed.holding:
        return "holding"
    return "completed"


def _latest_price(prices: dict[str, float], end: str) -> tuple[str, float] | None:
    candidates = [
        (dt, price) for dt, price in prices.items()
        if dt <= end
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])


def _days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days

