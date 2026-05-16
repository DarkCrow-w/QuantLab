"""Canonical schema for the data layer.

Defines column names/types, the Freq literal, and parquet KV-metadata helpers
used by store.py to track indicator versions per file.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import date
from typing import Iterable, Literal

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

Freq = Literal["day", "week", "month"]
ALL_FREQS: tuple[Freq, ...] = ("day", "week", "month")

OHLCV_COLUMNS: tuple[str, ...] = ("dt", "open", "high", "low", "close", "volume", "amount")

# Optional column appended for qfq drift detection (only when the source provides it).
ADJ_FACTOR_COL = "adj_factor"

OHLCV_DTYPES: dict[str, str] = {
    "open": "float64",
    "high": "float64",
    "low": "float64",
    "close": "float64",
    "volume": "float64",
    "amount": "float64",
    "adj_factor": "float64",
}

# Parquet KV-metadata key under which we record per-column indicator versions.
META_KEY_INDICATOR_VERSIONS = b"quant.indicator_versions"
META_KEY_DATA_VERSION = b"quant.data_version"
DATA_VERSION = "v1"


def volume_rows_in_hands(df: pd.DataFrame) -> pd.Series:
    """Identify rows whose volume is in lots while amount remains in yuan.

    For canonical share volume, ``amount / volume`` is close to the traded
    price. TDX lot volume makes that ratio roughly 100 times the price.
    """
    required = {"close", "volume", "amount"}
    if df is None or df.empty or not required.issubset(df.columns):
        return pd.Series(False, index=df.index if df is not None else None)
    close = pd.to_numeric(df["close"], errors="coerce")
    volume = pd.to_numeric(df["volume"], errors="coerce")
    amount = pd.to_numeric(df["amount"], errors="coerce")
    ratio = amount / volume / close
    valid = (close > 0) & (volume > 0) & (amount > 0)
    return (valid & ratio.between(50.0, 150.0)).fillna(False)


def normalize_kline(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce a raw fetched kline DataFrame to the canonical schema."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=list(OHLCV_COLUMNS))
    out = df.copy()
    if "dt" not in out.columns:
        raise ValueError("kline frame missing required column: dt")
    out["dt"] = pd.to_datetime(out["dt"]).dt.date
    for col, dtype in OHLCV_DTYPES.items():
        if col in out.columns:
            out[col] = out[col].astype(dtype)
    keep = [c for c in OHLCV_COLUMNS if c in out.columns]
    extras = [c for c in out.columns if c not in OHLCV_COLUMNS]
    out = out[keep + extras]
    out = out.drop_duplicates(subset=["dt"], keep="last").sort_values("dt").reset_index(drop=True)
    return out


def safe_write_parquet(df: pd.DataFrame, path: Path, indicator_versions: dict[str, str] | None = None) -> None:
    """Atomic parquet write via temp file + os.replace.

    Embeds indicator-version mapping in parquet KV-metadata so readers can
    detect stale columns when an indicator's version changes.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")

    table = pa.Table.from_pandas(df, preserve_index=False)
    meta: dict[bytes, bytes] = dict(table.schema.metadata or {})
    meta[META_KEY_DATA_VERSION] = DATA_VERSION.encode("utf-8")
    if indicator_versions is not None:
        meta[META_KEY_INDICATOR_VERSIONS] = json.dumps(indicator_versions, sort_keys=True).encode("utf-8")
    table = table.replace_schema_metadata(meta)

    # Small row groups make recent-window reads cheap while keeping files compact.
    pq.write_table(table, tmp, compression="snappy", row_group_size=256)
    tmp.replace(path)


def read_parquet_with_meta(
    path: Path,
    columns: Iterable[str] | None = None,
    start: date | None = None,
    end: date | None = None,
    tail: int | None = None,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Return a projected/filtered frame and its indicator versions."""
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=list(OHLCV_COLUMNS)), {}

    parquet = pq.ParquetFile(path)
    schema = parquet.schema_arrow
    requested = list(dict.fromkeys(columns)) if columns is not None else None
    read_columns = (
        [column for column in requested if column in schema.names]
        if requested is not None
        else None
    )

    row_groups = _tail_row_groups(parquet, tail, end) if tail and start is None else None
    if row_groups is not None:
        table = parquet.read_row_groups(row_groups, columns=read_columns)
    else:
        filters = []
        if start is not None:
            filters.append(("dt", ">=", start))
        if end is not None:
            filters.append(("dt", "<=", end))
        table = pq.read_table(path, columns=read_columns, filters=filters or None)

    df = table.to_pandas()
    if "dt" in df.columns:
        df["dt"] = pd.to_datetime(df["dt"]).dt.date
        if start is not None:
            df = df[df["dt"] >= start]
        if end is not None:
            df = df[df["dt"] <= end]
    if tail is not None:
        df = df.tail(max(0, tail))
    df = df.reset_index(drop=True)

    raw = (schema.metadata or {}).get(META_KEY_INDICATOR_VERSIONS)
    versions: dict[str, str] = json.loads(raw.decode("utf-8")) if raw else {}
    return df, versions


def _tail_row_groups(
    parquet: pq.ParquetFile,
    tail: int | None,
    end: date | None,
) -> list[int] | None:
    """Pick only trailing row groups needed for a recent-window read."""
    if not tail or parquet.metadata.num_row_groups <= 0:
        return None
    dt_index = parquet.schema_arrow.get_field_index("dt")
    if dt_index < 0:
        return None

    selected: list[int] = []
    remaining = tail
    for i in range(parquet.metadata.num_row_groups - 1, -1, -1):
        group = parquet.metadata.row_group(i)
        stats = group.column(dt_index).statistics
        if stats is None or not stats.has_min_max:
            return None
        group_min = _to_date(stats.min)
        group_max = _to_date(stats.max)
        if end is not None and group_min is not None and group_min > end:
            continue
        selected.append(i)
        # A group crossing end_date may contain very few eligible rows, so keep
        # one full window before it as well.
        if end is None or (group_max is not None and group_max <= end):
            remaining -= group.num_rows
        if remaining <= 0:
            break
    return sorted(selected) if selected else []


def _to_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        return value.date()  # type: ignore[no-any-return]
    return date.fromisoformat(str(value)[:10])
