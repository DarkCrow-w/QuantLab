"""Configurable language-model provider for QuantLab agents."""

from __future__ import annotations

from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from quant.config import get_settings


@lru_cache(maxsize=1)
def get_agent_model() -> BaseChatModel:
    settings = get_settings().agent

    if settings.provider == "deepseek":
        if not settings.deepseek_api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.model,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            max_tokens=settings.max_tokens,
            temperature=0.2,
            timeout=120,
            max_retries=2,
            stream_usage=False,
            extra_body={"thinking": {"type": "disabled"}},
        )

    if settings.provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.model,
            api_key=settings.anthropic_api_key,
            max_tokens=settings.max_tokens,
            temperature=0.2,
            timeout=120,
            max_retries=2,
        )

    raise RuntimeError(f"unsupported AGENT_PROVIDER: {settings.provider}")


def get_agent_runtime_status() -> dict:
    settings = get_settings().agent
    configured = (
        bool(settings.deepseek_api_key)
        if settings.provider == "deepseek"
        else bool(settings.anthropic_api_key)
        if settings.provider == "anthropic"
        else False
    )
    return {
        "enabled": configured,
        "provider": settings.provider,
        "model": settings.model,
        "configured": configured,
        "reason": None if configured else f"{settings.provider} API key is not configured",
    }


def reset_agent_model() -> None:
    get_agent_model.cache_clear()
