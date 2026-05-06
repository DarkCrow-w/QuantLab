"""选股专家 Sub-Agent。"""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from server.agent.prompts import SCREENING_AGENT_PROMPT
from server.agent.tools.screening_tools import screen_stocks_tool


def create_screening_agent(model: ChatAnthropic | None = None):
    """创建选股专家 Agent。"""
    if model is None:
        model = ChatAnthropic(model="claude-sonnet-4-20250514")

    return create_react_agent(
        model=model,
        tools=[screen_stocks_tool],
        prompt=SCREENING_AGENT_PROMPT,
        name="screening_agent",
    )
