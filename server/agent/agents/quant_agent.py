"""Standalone Quant-perspective agent."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.prebuilt import create_react_agent

from server.agent.model import get_agent_model
from server.agent.quant_skill import get_quant_agent_prompt
from server.agent.tools.analysis_tools import analyze_technicals_tool
from server.agent.tools.backtest_tools import (
    compare_backtests_tool,
    list_strategies_tool,
    run_backtest_tool,
)
from server.agent.tools.market_tools import (
    get_kline_data_tool,
    list_cached_stocks_tool,
    resolve_stock_symbol_tool,
)
from server.agent.tools.screening_tools import screen_stocks_tool


def create_quant_agent(
    model: BaseChatModel | None = None,
    checkpointer=None,
):
    return create_react_agent(
        model=model or get_agent_model(),
        tools=[
            resolve_stock_symbol_tool,
            analyze_technicals_tool,
            get_kline_data_tool,
            list_cached_stocks_tool,
            screen_stocks_tool,
            run_backtest_tool,
            compare_backtests_tool,
            list_strategies_tool,
        ],
        prompt=get_quant_agent_prompt(),
        name="quant_agent",
        checkpointer=checkpointer,
    )
