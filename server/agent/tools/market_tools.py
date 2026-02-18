"""行情数据相关 LangChain Tools — 包装 market_service 和 updater 函数。"""

from __future__ import annotations

import json
from typing import Optional

from langchain_core.tools import tool

from quant.data.updater import list_cached_symbols, fetch_all_a_symbols
from server.services.market_service import get_kline


@tool
def get_kline_data_tool(
    symbol: str,
    start_date: str,
    end_date: str,
) -> str:
    """获取股票 K 线数据（日线 OHLCV）。

    Args:
        symbol: 股票代码，例如 "600519"
        start_date: 开始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD

    Returns:
        K 线数据的 JSON 字符串，包含日期、开高低收、成交量
    """
    bars = get_kline(symbol, start_date, end_date)

    output = {
        "symbol": symbol,
        "bar_count": len(bars),
        "date_range": f"{start_date} ~ {end_date}",
        "bars": [
            {
                "dt": b.dt,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in bars[-60:]  # 最多返回最近 60 条，避免过多 token
        ],
    }
    if bars:
        closes = [b.close for b in bars]
        output["summary"] = {
            "latest_close": closes[-1],
            "period_high": max(b.high for b in bars),
            "period_low": min(b.low for b in bars),
            "period_return": round((closes[-1] - closes[0]) / closes[0], 4) if closes[0] > 0 else 0,
        }
    return json.dumps(output, ensure_ascii=False, default=str)


@tool
def list_cached_stocks_tool() -> str:
    """列出所有已缓存的股票数据（本地 Parquet 文件），包含代码、K 线数量、起止日期。

    Returns:
        缓存股票列表的 JSON 字符串
    """
    symbols = list_cached_symbols()
    output = {
        "total_cached": len(symbols),
        "stocks": symbols[:50],  # 最多展示 50 条
    }
    return json.dumps(output, ensure_ascii=False, default=str)


@tool
def get_all_a_stock_list_tool(source: str = "tushare") -> str:
    """获取全部 A 股股票列表。

    Args:
        source: 数据源，可选 "tushare" 或 "akshare"

    Returns:
        全 A 股列表的 JSON 字符串，包含代码和名称
    """
    stocks = fetch_all_a_symbols(source)
    output = {
        "total": len(stocks),
        "stocks": stocks[:100],  # 最多展示 100 条
    }
    return json.dumps(output, ensure_ascii=False, default=str)
