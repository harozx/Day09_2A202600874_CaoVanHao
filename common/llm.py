"""Shared LLM factory for all agents.

Uses OpenRouter as an OpenAI-compatible API, so any provider's model
can be selected via the OPENROUTER_MODEL env var.
"""

import os

from langchain_openai import ChatOpenAI


def get_llm(max_tokens: int = 1024) -> ChatOpenAI:
    """Return a ChatOpenAI client pointed at OpenRouter.

    Args:
        max_tokens: Maximum tokens for the response. Lower values reduce latency.
    """
    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash"),
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        openai_api_base="https://openrouter.ai/api/v1",
        max_tokens=max_tokens,
        temperature=0.3,
    )