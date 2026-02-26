"""行情数据专家 Sub-Agent。"""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from server.agent.prompts import MARKET_AGENT_PROMPT
from server.agent.tools.analysis_tools import analyze_technicals_tool
from server.agent.tools.market_tools import (
    get_all_a_stock_list_tool,
    get_kline_data_tool,
    list_cached_stocks_tool,
)


def create_market_agent(model: ChatAnthropic | None = None):
    """创建行情数据专家 Agent。"""
    if model is None:
        model = ChatAnthropic(model="claude-sonnet-4-20250514")

    return create_react_agent(
        model=model,
        tools=[
            get_kline_data_tool,
            list_cached_stocks_tool,
            get_all_a_stock_list_tool,
            analyze_technicals_tool,
        ],
        prompt=MARKET_AGENT_PROMPT,
        name="market_agent",
    )
