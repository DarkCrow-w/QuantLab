"""Source 协议 — 数据拉取层抽象。

与 ``quant.data.base.DataFeed`` 的区别：
- ``DataFeed`` 是面向回测引擎的迭代器（``subscribe`` / ``update`` / ``has_more``）
- ``Source`` 仅负责"从外部拉一段时间序列"，不维护游标，纯函数接口

更新器从 ``Source`` 拉数据写入 ``DataStore``，回测引擎从 ``DataStore`` 读，
两者解耦。
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class Source(Protocol):
    """数据源协议 — TDX/AKShare/Tushare/CSV 等都需实现。"""

    name: str

    def fetch_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """返回标准化的日线 DataFrame：``[dt, open, high, low, close, volume, amount]``。

        Args:
            symbol: 6 位股票代码（不含后缀）
            start:  ``YYYYMMDD`` 起始日期（含）
            end:    ``YYYYMMDD`` 结束日期（含）
        """
        ...

    def list_symbols(self) -> list[dict]:
        """返回 A 股全市场代码列表，每条 ``{symbol, name, market, list_date?, industry?}``。

        若该数据源不支持，返回空列表。
        """
        ...
