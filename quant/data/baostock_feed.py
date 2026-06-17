"""Baostock 数据源 — 免费、无 token，但全局 session 非线程安全，仅支持串行调用。"""
from __future__ import annotations

import atexit
import threading
from collections import defaultdict
from datetime import date

import baostock as bs
import pandas as pd
from loguru import logger

from quant.core.bar import Bar
from quant.core.events import MarketEvent
from .base import DataFeed
from .symbol_filter import filter_a_share_rows, is_a_share_symbol
from .cache import load_cache, save_cache

# Baostock 用 module-global session，登录/查询/登出共享同一个 socket。
# 多线程并发查询会导致 socket 数据流错乱（utf-8 decode error / zlib invalid distance）。
# 因此所有调用都走单一锁，强制串行化。
_BS_LOCK = threading.Lock()
_logged_in = False


def _ensure_login() -> None:
    """首次调用时登录，进程退出时自动 logout。"""
    global _logged_in
    if _logged_in:
        return
    rs = bs.login()
    if rs.error_code != "0":
        raise RuntimeError(f"baostock login failed: {rs.error_msg}")
    atexit.register(bs.logout)
    _logged_in = True


def _to_bs_code(symbol: str) -> str:
    """600519 -> sh.600519, 000001/300xxx -> sz.xxx"""
    return f"sh.{symbol}" if symbol.startswith(("6", "9")) else f"sz.{symbol}"


def _fetch_daily(symbol: str, start: str, end: str) -> pd.DataFrame:
    """从 Baostock 获取日线数据，返回标准列名 DataFrame。

    Args:
        symbol: 6 位代码, e.g. "600519"
        start, end: YYYYMMDD（与 updater.py 路由契约一致），内部转 YYYY-MM-DD
    """
    start_dash = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
    end_dash = f"{end[:4]}-{end[4:6]}-{end[6:8]}"
    bs_code = _to_bs_code(symbol)
    logger.info(f"Fetching {symbol} ({bs_code}) from Baostock ({start_dash} ~ {end_dash})")

    with _BS_LOCK:
        _ensure_login()
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume,amount",
            start_date=start_dash,
            end_date=end_dash,
            frequency="d",
            adjustflag="2",  # 2 = 前复权
        )
        if rs.error_code != "0":
            raise RuntimeError(f"baostock query failed for {symbol}: {rs.error_msg}")
        rows: list[list[str]] = []
        while rs.next():
            rows.append(rs.get_row_data())

    if not rows:
        raise ValueError(f"No data returned for {symbol} from Baostock")

    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume", "amount"])
    for col in ("open", "high", "low", "close", "volume", "amount"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # 停牌行 volume/amount 为空 → coerce 后 NaN，整行剔除
    df = df.dropna(subset=["close"])
    df["dt"] = pd.to_datetime(df["date"]).dt.date
    df = df[["dt", "open", "high", "low", "close", "volume", "amount"]]
    df = df.sort_values("dt").reset_index(drop=True)
    return df


def fetch_all_a_symbols_baostock() -> list[dict]:
    """从 Baostock 获取全 A 股上市股票列表（剥掉 sh./sz. 前缀返回 6 位代码）。"""
    with _BS_LOCK:
        _ensure_login()
        rs = bs.query_stock_basic()
        if rs.error_code != "0":
            raise RuntimeError(f"baostock stock_basic failed: {rs.error_msg}")
        rows: list[list[str]] = []
        while rs.next():
            rows.append(rs.get_row_data())

    if not rows:
        return []
    df = pd.DataFrame(rows, columns=rs.fields)
    # 仅保留普通 A 股且在市，剔除指数、板块、基金和 B 股代码。
    df = df[df["status"] == "1"]
    df = df[df["type"] == "1"]  # 1 = 股票
    records: list[dict] = []
    for _, r in df.iterrows():
        code = r["code"]
        sym = code.split(".", 1)[1]
        if not is_a_share_symbol(sym):
            continue
        records.append({
            "symbol": sym,
            "name": r.get("code_name", ""),
            "industry": "",
            "market": "SH" if code.startswith("sh.") else "SZ",
            "list_date": r.get("ipoDate", ""),
        })
    return filter_a_share_rows(records)


class BaostockFeed(DataFeed):
    """Daily-bar data feed backed by Baostock with Parquet caching."""

    def __init__(self, start_date: str, end_date: str, use_cache: bool = True) -> None:
        self.start_date = start_date
        self.end_date = end_date
        self.use_cache = use_cache
        self._symbols: list[str] = []
        self._data: dict[str, pd.DataFrame] = {}
        self._dates: list[date] = []
        self._cursor: int = 0
        self._history: dict[str, list[Bar]] = defaultdict(list)

    def subscribe(self, symbols: list[str]) -> None:
        self._symbols = symbols
        for sym in symbols:
            df = None
            if self.use_cache:
                df = load_cache(sym)
                if df is not None:
                    df = df[(df["dt"] >= date.fromisoformat(self.start_date))
                            & (df["dt"] <= date.fromisoformat(self.end_date))]
                    if len(df) == 0:
                        df = None
            if df is None:
                df = _fetch_daily(
                    sym,
                    self.start_date.replace("-", ""),
                    self.end_date.replace("-", ""),
                )
                if self.use_cache:
                    save_cache(sym, df)
            self._data[sym] = df.reset_index(drop=True)
            logger.info(f"Subscribed {sym}: {len(df)} bars")

        all_dates: set[date] = set()
        for df in self._data.values():
            all_dates.update(df["dt"].tolist())
        self._dates = sorted(all_dates)
        self._cursor = 0

    def has_more(self) -> bool:
        return self._cursor < len(self._dates)

    def update(self) -> MarketEvent | None:
        if not self.has_more():
            return None
        current_dt = self._dates[self._cursor]
        self._cursor += 1
        bars: dict[str, Bar] = {}
        for sym in self._symbols:
            df = self._data[sym]
            row = df[df["dt"] == current_dt]
            if row.empty:
                continue
            r = row.iloc[0]
            bar = Bar(
                symbol=sym,
                dt=current_dt,
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r["volume"]),
                amount=float(r.get("amount", 0)),
            )
            bars[sym] = bar
            self._history[sym].append(bar)
        if not bars:
            return self.update()
        return MarketEvent(dt=current_dt, bars=bars)

    def get_latest_bars(self, symbol: str, n: int = 1) -> list[Bar]:
        history = self._history.get(symbol, [])
        return history[-n:] if n <= len(history) else list(history)
