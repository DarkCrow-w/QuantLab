"""Source adapters and feed implementations backed by DataStore."""
from __future__ import annotations

from .akshare import AKShareSource
from .base import Source
from .csv import CSVSource
from .store_feed import StoreFeed
from .tdx import TDXSource
from .tushare import TushareSource

__all__ = [
    "AKShareSource",
    "CSVSource",
    "Source",
    "StoreFeed",
    "TDXSource",
    "TushareSource",
]


def default_sources() -> list[Source]:
    """优先级顺序：TDX → AKShare → Tushare（与 updater 默认回退链一致）。"""
    return [TDXSource(), AKShareSource(), TushareSource()]
