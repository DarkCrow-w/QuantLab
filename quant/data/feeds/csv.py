"""CSV Source — 测试/离线用。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..symbols import normalize


class CSVSource:
    name = "csv"

    def __init__(self, csv_dir: str | Path) -> None:
        self.csv_dir = Path(csv_dir)

    def fetch_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        sym = normalize(symbol)
        path = self.csv_dir / f"{sym}.csv"
        if not path.exists():
            raise FileNotFoundError(f"CSV not found: {path}")
        df = pd.read_csv(path, parse_dates=["dt"])
        df["dt"] = df["dt"].dt.date
        start_d = pd.Timestamp(start).date()
        end_d = pd.Timestamp(end).date()
        df = df[(df["dt"] >= start_d) & (df["dt"] <= end_d)]
        return df.sort_values("dt").reset_index(drop=True)

    def list_symbols(self) -> list[dict]:
        return [{"symbol": p.stem, "name": "", "market": ""} for p in self.csv_dir.glob("*.csv")]
