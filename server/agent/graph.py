"""LangGraph Supervisor Graph — 多 Agent 协调中枢。"""

from __future__ import annotations

import os
from functools import lru_cache

from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph_supervisor import create_supervisor

from server.agent.agents.backtest_agent import create_backtest_agent
from server.agent.agents.market_agent import create_market_agent
from server.agent.agents.screening_agent import create_screening_agent
from server.agent.prompts import SUPERVISOR_SYSTEM_PROMPT


@lru_cache(maxsize=1)
def _get_model() -> ChatAnthropic:
    """获取 LLM 实例（单例）。"""
    return ChatAnthropic(
        model=os.getenv("AGENT_MODEL", "claude-sonnet-4-20250514"),
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        max_tokens=4096,
    )


@lru_cache(maxsize=1)
def _get_checkpointer() -> MemorySaver:
    """获取检查点存储（单例，Phase 5 可替换为 PostgresSaver）。"""
    return MemorySaver()


def build_graph():
    """构建并编译 supervisor multi-agent graph。

    Returns:
        编译后的 LangGraph CompiledGraph，可通过 .invoke() 或 .stream() 调用。
    """
    model = _get_model()
    checkpointer = _get_checkpointer()

    # 创建各专业 sub-agent
    backtest_agent = create_backtest_agent(model)
    screening_agent = create_screening_agent(model)
    market_agent = create_market_agent(model)

    # 创建 supervisor，将 sub-agents 注册为可调度对象
    supervisor = create_supervisor(
        agents=[backtest_agent, screening_agent, market_agent],
        model=model,
        prompt=SUPERVISOR_SYSTEM_PROMPT,
    )

    # 编译 graph，附加检查点存储
    graph = supervisor.compile(checkpointer=checkpointer)
    return graph


# 全局 graph 实例（延迟初始化）
_graph = None


def get_graph():
    """获取全局 graph 实例（延迟初始化）。"""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
