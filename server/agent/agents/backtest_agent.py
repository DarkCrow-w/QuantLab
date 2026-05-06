"""回测专家 Sub-Agent。"""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from server.agent.prompts import BACKTEST_AGENT_PROMPT
from server.agent.tools.backtest_tools import (
    compare_backtests_tool,
    list_strategies_tool,
    run_backtest_tool,
)


def create_backtest_agent(model: ChatAnthropic | None = None):
    """创建回测专家 Agent。"""
    if model is None:
        model = ChatAnthropic(model="claude-sonnet-4-20250514")

    return create_react_agent(
        model=model,
        tools=[run_backtest_tool, list_strategies_tool, compare_backtests_tool],
        prompt=BACKTEST_AGENT_PROMPT,
        name="backtest_agent",
    )
