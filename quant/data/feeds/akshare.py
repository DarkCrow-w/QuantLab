"""AKShare Source — 通过 akshare 拉取东方财富日线。"""
from __future__ import annotations

import pandas as pd
from loguru import logger

from ..symbol_filter import filter_a_share_rows, is_a_share_symbol
from ..symbols import normalize

_COL_MAP = {
    "日期": "dt", "开盘": "open", "收盘": "close",
    "最高": "high", "最低": "low",
    "成交量": "volume", "成交额": "amount",
}


class AKShareSource:
    name = "akshare"

    def fetch_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        import akshare as ak

        sym = normalize(symbol)
        df = ak.stock_zh_a_hist(
            symbol=sym, period="daily", start_date=start, end_date=end, adjust="qfq",
        )
        if df is None or df.empty:
            raise ValueError(f"No data returned for {sym} from AKShare")
        df = df.rename(columns=_COL_MAP)
        df["dt"] = pd.to_datetime(df["dt"]).dt.date
        # AKShare 的「成交量」是手；标准 schema 要求 volume 单位为股。「成交额」已是元。
        df["volume"] = df["volume"].astype(float) * 100
        df["amount"] = df["amount"].astype(float)
        df = df[["dt", "open", "high", "low", "close", "volume", "amount"]]
        return df.sort_values("dt").reset_index(drop=True)

    def list_symbols(self) -> list[dict]:
        import akshare as ak

        try:
            df = ak.stock_info_a_code_name()
        except Exception as e:
            logger.warning(f"AKShare list_symbols failed: {e}")
            return []
        out: list[dict] = []
        for r in df.itertuples(index=False):
            code = str(r.code).zfill(6)
            if not code.isdigit() or len(code) != 6:
                continue
            if not is_a_share_symbol(code):
                continue
            if code.startswith(("4", "8", "920")):
                m = "BJ"
            elif code.startswith("6"):
                m = "SH"
            elif code.startswith(("0", "3")):
                m = "SZ"
            else:
                continue
            out.append({"symbol": code, "name": getattr(r, "name", ""), "market": m})
        return filter_a_share_rows(out)
