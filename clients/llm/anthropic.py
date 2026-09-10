"""Anthropic-backed LLM client: server-side fallbacks, `web_fetch` & `pause_turn` resumption."""

from typing import ClassVar, Optional, Type

from anthropic import APIError, AsyncAnthropic, RateLimitError

from config import ANTHROPIC_API_KEY, ANTHROPIC_LLM_MODEL

from .base import BaseLLMClient, LLMRefusalError


class AnthropicClient(BaseLLMClient):
    """Answers `@bro` prompts with Claude, via the Anthropic SDK's `AsyncAnthropic` client."""

    # Anthropic's server-side web fetch tool. It can only retrieve URLs already present in the
    # conversation, and is attached only when the message tagging the bot carries one (see
    # `fetchable_hosts`), pinned to that link's host — so the bot never reads a URL nobody handed it.
    WEB_FETCH_TOOL_TYPE = "web_fetch_20260209"
    WEB_FETCH_MAX_USES = 2
    WEB_FETCH_MAX_CONTENT_TOKENS = 8000

    # A server-side tool loop which hits its iteration cap stops with `pause_turn` and must be
    # re-sent to continue. Chat replies are latency-sensitive, so resumes are kept few.
    MAX_PAUSE_TURN_RESUMES = 2

    LINK_TOOL_NAME: ClassVar[str] = "web_fetch"
    RATE_LIMIT_ERROR: ClassVar[Type[Exception]] = RateLimitError
    API_ERROR: ClassVar[Type[Exception]] = APIError

    def __init__(self):
        """Initialize the Anthropic client with API credentials"""
        super().__init__()
        self.client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        self.model = ANTHROPIC_LLM_MODEL
        self.beta = "server-side-fallback-2026-07-01"

    async def generate_response(
        self,
        messages,
        max_tokens=4096,
        fetch_hosts: Optional[list] = None,
        chat_message: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate a response for a single prompt.

        Thinking is on by default on Claude Opus 5, and `max_tokens` caps thinking *plus*
        reply text, hence the headroom; brevity of the reply itself is enforced by the
        persona prompt. Chat replies are latency-sensitive, so effort is kept low.

        :param messages: The input messages to send to the LLM
        :param max_tokens: Maximum number of tokens to generate, including thinking
        :param Optional[list] fetch_hosts: Hosts the LLM may read with the web fetch tool. Empty or
            omitted means the tool is not offered at all, so no link can be fetched.
        :param Optional[str] chat_message: Unused — the link gate is already applied upstream, in
            `fetch_hosts`. Accepted so both providers share one signature.

        :raises LLMRefusalError: If the prompt is declined and no fallback model rescues it.

        :returns: str Generated response text
        """
        request = {
            "max_tokens": max_tokens,
            "system": self.system_prompt(fetch_hosts),
            "messages": messages,
            "model": self.model,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "medium"},
            "betas": [self.beta],
            "fallbacks": "default",
        }
        if fetch_hosts:
            request["tools"] = [
                {
                    "type": self.WEB_FETCH_TOOL_TYPE,
                    "name": "web_fetch",
                    "max_uses": self.WEB_FETCH_MAX_USES,
                    # Pinning the tool to the hosts the user handed us means a fetched page can't
                    # walk the bot off to a URL nobody in chat asked about.
                    "allowed_domains": fetch_hosts,
                    "max_content_tokens": self.WEB_FETCH_MAX_CONTENT_TOKENS,
                }
            ]
        message = await self.client.beta.messages.create(**request)
        for _ in range(self.MAX_PAUSE_TURN_RESUMES):
            if message.stop_reason != "pause_turn":
                break
            # The paused turn resumes by re-sending it as-is; adding a nudge of our own would
            # derail it, as the API detects the trailing tool use and picks up where it left off.
            request["messages"] = [*request["messages"], {"role": "assistant", "content": message.content}]
            message = await self.client.beta.messages.create(**request)
        self._log_fallback(message)
        if message.stop_reason == "refusal":
            category = message.stop_details.category if message.stop_details else None
            raise LLMRefusalError(f"Prompt declined (category: {category or 'unspecified'})")
        raw_response = self._reply_text(message)
        if raw_response:
            return self.format_response_for_html(raw_response)
        return None

    @staticmethod
    def _reply_text(message) -> Optional[str]:
        """
        Pull the reply out of a response whose content may hold more than the reply.

        Thinking, fallback and web fetch blocks carry no reply text, and a turn which used a tool
        also opens with a throwaway preamble ("lemme peep that link") *before* the tool call. Only
        the text after the final non-text block is the answer, so everything earlier is dropped.

        :param message: Response returned by the Anthropic API.

        :returns Optional[str]: The reply text, if the response contained any.
        """
        last_non_text = max(
            (index for index, block in enumerate(message.content) if block.type != "text"),
            default=-1,
        )
        reply = "\n\n".join(block.text for block in message.content[last_non_text + 1 :])
        return reply or None

    @staticmethod
    def _log_fallback(message) -> None:
        """
        Note which model served the reply whenever a fallback model stepped in.

        :param message: Response returned by the Anthropic API.

        :returns: None
        """
        # Imported lazily: `logger` imports `clients`, so a module-level import would cycle.
        from logger import LOGGER

        iterations = message.usage.iterations or []
        if not any(iteration.type == "fallback_message" for iteration in iterations):
            return
        # Sticky-routed replies are served by the fallback model without a `fallback` block.
        declined_by = next(
            (block.from_.model for block in message.content if block.type == "fallback"),
            "a declined model",
        )
        LOGGER.warning(f"LLM request fell back from {declined_by} to {message.model}")

    async def close(self) -> None:
        """
        Close the underlying `httpx` client owned by the Anthropic SDK.

        :returns: None
        """
        await self.client.close()
