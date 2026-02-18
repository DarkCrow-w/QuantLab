"""选股相关 LangChain Tools — 包装 screening_service 现有函数。"""

from __future__ import annotations

import json
from typing import Optional

from langchain_core.tools import tool

from server.models.screening import ScreenRequest
from server.services.screening_service import run_screening


@tool
def screen_stocks_tool(
    strategy: str,
    strategy_params: Optional[dict] = None,
    scan_date: Optional[str] = None,
    lookback: int = 120,
) -> str:
    """扫描所有缓存股票，找出符合策略买入信号的股票。

    Args:
        strategy: 策略名称，可选值: ma_cross, vol_kdj_bbi, bbi_kdj_trend
        strategy_params: 策略参数字典（可选）
        scan_date: 扫描日期，格式 YYYY-MM-DD，默认今天
        lookback: 回看天数，默认 120

    Returns:
        选股结果的 JSON 字符串，包含匹配的股票列表及信号强度
    """
    req = ScreenRequest(
        strategy=strategy,
        strategy_params=strategy_params or {},
        scan_date=scan_date,
        lookback=lookback,
    )
    result = run_screening(req)

    output = {
        "strategy": result.strategy,
        "scan_date": result.scan_date,
        "total_scanned": result.total_scanned,
        "match_count": len(result.matches),
        "elapsed_seconds": result.elapsed_seconds,
        "matches": [
            {
                "symbol": m.symbol,
                "signal_date": m.signal_date,
                "close": m.close,
                "volume": m.volume,
                "amount": m.amount,
                "strength": m.strength,
            }
            for m in result.matches[:30]  # 最多展示前 30 条
        ],
    }
    return json.dumps(output, ensure_ascii=False, default=str)
