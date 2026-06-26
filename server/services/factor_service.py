from __future__ import annotations

import json
import math
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd

from quant.data import get_store
from quant.screening import FACTOR_DEFS
from server.models.factor import (
    FactorMiningItem,
    FactorMiningRequest,
    FactorMiningResult,
    ManagedFactor,
    ManagedFactorDraft,
)

_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "meta" / "factors.sqlite3"


class FactorStore:
    def __init__(self, path: Path | str = _DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS factors (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    key TEXT NOT NULL UNIQUE,
                    label TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    expression TEXT NOT NULL DEFAULT '',
                    default_weight REAL NOT NULL DEFAULT 1,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def list(self) -> list[ManagedFactor]:
        self._seed_builtin()
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM factors ORDER BY source, key").fetchall()
        return [self._from_row(row) for row in rows]

    def get(self, factor_id: str) -> ManagedFactor | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM factors WHERE id = ?", (factor_id,)).fetchone()
        return self._from_row(row) if row else None

    def save(self, draft: ManagedFactorDraft, factor_id: str | None = None) -> ManagedFactor:
        now = datetime.now().isoformat(timespec="seconds")
        factor_id = factor_id or uuid.uuid4().hex
        existing = self.get(factor_id)
        created_at = existing.created_at if existing else now
        source = existing.source if existing else "custom"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO factors(
                    id,source,key,label,category,description,expression,default_weight,enabled,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    key=excluded.key,
                    label=excluded.label,
                    category=excluded.category,
                    description=excluded.description,
                    expression=excluded.expression,
                    default_weight=excluded.default_weight,
                    enabled=excluded.enabled,
                    updated_at=excluded.updated_at
                """,
                (
                    factor_id,
                    source,
                    draft.key.strip(),
                    draft.label.strip(),
                    draft.category.strip() or "custom",
                    draft.description.strip(),
                    draft.expression.strip(),
                    draft.default_weight,
                    int(draft.enabled),
                    created_at,
                    now,
                ),
            )
        return self.get(factor_id)  # type: ignore[return-value]

    def delete(self, factor_id: str) -> bool:
        factor = self.get(factor_id)
        if factor and factor.source == "builtin":
            raise ValueError("builtin factors cannot be deleted")
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM factors WHERE id = ?", (factor_id,))
        return cursor.rowcount > 0

    def _seed_builtin(self) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            for item in FACTOR_DEFS:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO factors(
                        id,source,key,label,category,description,expression,default_weight,enabled,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        f"builtin_{item['key']}",
                        "builtin",
                        item["key"],
                        item["label"],
                        "score",
                        item.get("desc", ""),
                        "",
                        float(item.get("default_weight", 1)),
                        1,
                        now,
                        now,
                    ),
                )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ManagedFactor:
        return ManagedFactor(
            id=row["id"],
            source=row["source"],
            key=row["key"],
            label=row["label"],
            category=row["category"],
            description=row["description"],
            expression=row["expression"],
            default_weight=float(row["default_weight"]),
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def mine_factors(req: FactorMiningRequest) -> FactorMiningResult:
    store = get_store()
    symbols = req.symbols or store.list_symbols("day")
    symbols = symbols[:300]
    candidates = _candidate_factors()
    values: dict[str, list[tuple[float, float]]] = {key: [] for key in candidates}
    warnings: list[str] = []

    for symbol in symbols:
        df = store.get_kline(
            symbol,
            freq="day",
            with_indicators=True,
            tail=req.lookback + req.forward_days + 5,
        )
        if df.empty or len(df) < req.min_samples + req.forward_days:
            continue
        frame = df.copy().reset_index(drop=True)
        future_return = frame["close"].shift(-req.forward_days) / frame["close"] - 1
        usable = frame.iloc[:-req.forward_days].copy()
        target = future_return.iloc[:-req.forward_days]
        for key, fn in candidates.items():
            try:
                series = fn(usable)
                pairs = (
                    pd.DataFrame({"factor": series, "ret": target})
                    .replace([math.inf, -math.inf], pd.NA)
                    .dropna()
                )
                values[key].extend(
                    (float(row.factor), float(row.ret)) for row in pairs.itertuples(index=False)
                )
            except Exception as exc:
                if len(warnings) < 5:
                    warnings.append(f"{symbol} {key}: {exc}")

    items: list[FactorMiningItem] = []
    for key, pairs in values.items():
        label, category = _candidate_meta(key)
        samples = len(pairs)
        ic: float | None = None
        if samples >= req.min_samples:
            frame = pd.DataFrame(pairs, columns=["factor", "ret"])
            corr = frame["factor"].corr(frame["ret"], method="spearman")
            if pd.notna(corr):
                ic = round(float(corr), 4)
        items.append(
            FactorMiningItem(
                key=key,
                label=label,
                category=category,
                samples=samples,
                ic=ic,
                abs_ic=round(abs(ic), 4) if ic is not None else None,
                coverage=round(samples / max(1, len(symbols) * req.lookback), 4),
                direction="positive" if (ic or 0) >= 0 else "negative",
            )
        )
    items.sort(key=lambda item: item.abs_ic or 0, reverse=True)
    return FactorMiningResult(
        symbols=len(symbols),
        lookback=req.lookback,
        forward_days=req.forward_days,
        items=items,
        warnings=warnings,
    )


def _candidate_factors() -> dict[str, Callable[[pd.DataFrame], pd.Series]]:
    return {
        "momentum_20": lambda df: df["close"] / df["close"].shift(20) - 1,
        "momentum_60": lambda df: df["close"] / df["close"].shift(60) - 1,
        "volatility_20": lambda df: df["close"].pct_change().rolling(20).std(),
        "volume_ratio_20": lambda df: df["volume"] / df["volume"].rolling(20).mean(),
        "ma_gap_20": lambda df: df["close"] / df["close"].rolling(20).mean() - 1,
        "turnover_amount_20": lambda df: df.get("amount", df["volume"]).rolling(20).mean(),
    }


def _candidate_meta(key: str) -> tuple[str, str]:
    meta = {
        "momentum_20": ("20日动量", "momentum"),
        "momentum_60": ("60日动量", "momentum"),
        "volatility_20": ("20日波动率", "risk"),
        "volume_ratio_20": ("20日量比", "volume"),
        "ma_gap_20": ("20日均线偏离", "trend"),
        "turnover_amount_20": ("20日成交额均值", "liquidity"),
    }
    return meta[key]


_STORE: FactorStore | None = None


def get_factor_store() -> FactorStore:
    global _STORE
    if _STORE is None:
        _STORE = FactorStore()
    return _STORE
