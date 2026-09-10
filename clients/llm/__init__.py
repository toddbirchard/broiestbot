"""LLM client for interacting with language models like Anthropic's Claude & OpenAI's ChatGPT."""

from typing import Callable, Dict

from config import LLM_TYPE

from .anthropic import AnthropicClient
from .base import BaseLLMClient, LLMRefusalError
from .openai import OpenAIClient

__all__ = ["AnthropicClient", "BaseLLMClient", "LLMClient", "LLMRefusalError", "OpenAIClient"]

#: `LLM_TYPE` values to the client each one builds. Adding a provider is a subclass of
#: `BaseLLMClient` plus a row here — nothing downstream branches on which one is live.
LLM_CLIENTS: Dict[str, Callable[[], BaseLLMClient]] = {
    "claude": AnthropicClient,
    "chatgpt": OpenAIClient,
}


def LLMClient() -> BaseLLMClient:  # noqa: N802 — a factory standing in for the class it replaced.
    """
    Build the LLM client `config.LLM_TYPE` asks for.

    Callers get a `BaseLLMClient` and never learn which provider answered; the two share a persona,
    history formatting and link gating, and agree on nothing else.

    :raises ValueError: If `LLM_TYPE` names a provider which has no client.

    :returns BaseLLMClient: A client for the configured provider.
    """
    llm_type = (LLM_TYPE or "").strip().lower()
    if llm_type not in LLM_CLIENTS:
        raise ValueError(f"Unsupported LLM_TYPE '{LLM_TYPE}'; expected one of {sorted(LLM_CLIENTS)}")
    return LLM_CLIENTS[llm_type]()
