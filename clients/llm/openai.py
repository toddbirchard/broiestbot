"""OpenAI-backed LLM client: the Responses API, plus `web_search` & vision on a link from chat."""

from typing import ClassVar, List, Optional, Type

from openai import APIError, AsyncOpenAI, BadRequestError, RateLimitError

from config import CHATGPT_API_KEY, CHATGPT_LLM_MODEL

from .base import BaseLLMClient, LLMRefusalError


class OpenAIClient(BaseLLMClient):
    """Answers `@bro` prompts with ChatGPT, via the OpenAI SDK's `AsyncOpenAI` client."""

    # OpenAI's hosted web search tool, the nearest analogue to Anthropic's `web_fetch`. It is
    # attached only when the message tagging the bot carries a link (see `fetchable_hosts`) and is
    # pinned to that link's host, so the bot never goes reading a site nobody in chat posted. Note
    # this is a *search* scoped to the host rather than a fetch of that exact URL: the model can
    # answer from a neighbouring page on the same site.
    WEB_SEARCH_TOOL_TYPE = "web_search"
    WEB_SEARCH_MAX_CALLS = 2
    WEB_SEARCH_CONTEXT_SIZE = "low"

    # Vision. `VISION_MAX_IMAGES` is inherited from `BaseLLMClient`; `low` detail keeps each image
    # to ~85 tokens, enough to answer "what is this" without the latency (or the bill) of shipping
    # every gif in the backlog at full resolution.
    VISION_IMAGE_DETAIL = "low"

    # Chat replies are latency-sensitive, so the model is told to think as little as it can.
    REASONING_EFFORT = "low"

    LINK_TOOL_NAME: ClassVar[str] = "web_search"
    RATE_LIMIT_ERROR: ClassVar[Type[Exception]] = RateLimitError
    API_ERROR: ClassVar[Type[Exception]] = APIError

    def __init__(self):
        """Initialize the OpenAI client with API credentials"""
        super().__init__()
        self.client = AsyncOpenAI(api_key=CHATGPT_API_KEY)
        self.model = CHATGPT_LLM_MODEL

    async def generate_response(
        self,
        messages,
        max_tokens=4096,
        fetch_hosts: Optional[list] = None,
        chat_message: Optional[str] = None,
        room_name: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate a response for a single prompt.

        `max_output_tokens` caps reasoning *plus* reply text, hence the headroom; brevity of the
        reply itself is enforced by the persona prompt.

        :param messages: The input messages to send to the LLM
        :param max_tokens: Maximum number of tokens to generate, including reasoning
        :param Optional[list] fetch_hosts: Hosts the LLM may read with the web search tool. Empty or
            omitted means the tool is not offered at all, so no link can be read.
        :param Optional[str] chat_message: The raw message which tagged the bot, used to decide
            whether this prompt is about an image. Omitted means no image is ever attached.
        :param Optional[str] room_name: Room the prompt was sent from, used to pick that room's
            active persona.

        :raises LLMRefusalError: If the model declines the prompt.

        :returns Optional[str]: HTML-formatted reply, if the response contained any text.
        """
        images = self._vision_images(messages, chat_message)
        request = {
            "model": self.model,
            "instructions": self.system_prompt(fetch_hosts, room_name),
            "input": messages,
            "max_output_tokens": max_tokens,
            "reasoning": {"effort": self.REASONING_EFFORT},
            # The room is private; there's no reason to leave its chat logs sitting in a dashboard.
            "store": False,
        }
        if fetch_hosts:
            request["tools"] = [
                {
                    "type": self.WEB_SEARCH_TOOL_TYPE,
                    # Pinning the search to the hosts the user handed us means a read page can't
                    # walk the bot off to a site nobody in chat asked about.
                    "filters": {"allowed_domains": fetch_hosts},
                    "search_context_size": self.WEB_SEARCH_CONTEXT_SIZE,
                }
            ]
            # The hosted tool loop runs server-side to completion, so it is bounded here rather
            # than resumed turn by turn the way Anthropic's is.
            request["max_tool_calls"] = self.WEB_SEARCH_MAX_CALLS
        if images:
            request["input"] = self._attach_images(messages, images)
            request["instructions"] += self.vision_prompt
        response = await self._create(request, images)
        refusal = self._refusal(response)
        if refusal:
            raise LLMRefusalError(f"Prompt declined ({refusal})")
        raw_response = self._reply_text(response)
        if raw_response:
            return self.format_response_for_html(raw_response)
        return None

    async def _create(self, request: dict, images: List[str]):
        """
        Send the request, dropping the images rather than the whole reply if they're rejected.

        An image URL is whatever somebody typed into chat: it can 404, sit behind hotlink
        protection, or point at an HTML page which merely looked like an image. OpenAI answers all
        of those with a 400 for the *request*, so without this a bad link costs the user their
        answer instead of just the picture.

        :param dict request: Fully-built request kwargs.
        :param List[str] images: Images attached to it, if any.

        :returns: Response returned by the OpenAI Responses API.
        """
        try:
            return await self.client.responses.create(**request)
        except BadRequestError as e:
            if not images:
                raise
            # Imported lazily: `logger` imports `clients`, so a module-level import would cycle.
            from logger import LOGGER

            LOGGER.warning(f"Retrying LLM request without unreadable image(s) {images}: {e}")
            request["input"] = [dict(message) for message in request["input"]]
            for message in request["input"]:
                if not isinstance(message["content"], str):
                    message["content"] = "\n".join(
                        part["text"] for part in message["content"] if part["type"] == "input_text"
                    )
            request["instructions"] = request["instructions"].removesuffix(self.vision_prompt)
            return await self.client.responses.create(**request)

    def _attach_images(self, messages, images: List[str]) -> list:
        """
        Hoist the images onto the turn which tagged the bot.

        They are attached to the last *user* turn rather than rewritten into whichever message
        carried the link, because the bot posts images too (`!gif`) and an `assistant` turn cannot
        hold an `input_image`. The caller's messages are left untouched.

        :param messages: The formatted chat history, oldest first.
        :param List[str] images: Image URLs to attach.

        :returns list: A copy of the history with the images attached, or it unchanged if there is
            no user turn to attach them to.
        """
        target = next(
            (index for index in reversed(range(len(messages))) if messages[index].get("role") == "user"),
            None,
        )
        if target is None:
            return messages
        attached = list(messages)
        attached[target] = {
            **messages[target],
            "content": [
                {"type": "input_text", "text": messages[target]["content"]},
                *({"type": "input_image", "image_url": url, "detail": self.VISION_IMAGE_DETAIL} for url in images),
            ],
        }
        return attached

    @staticmethod
    def _reply_text(response) -> Optional[str]:
        """
        Pull the reply out of a response whose output may hold more than the reply.

        Reasoning and web search items carry no reply text, and a turn which searched also opens
        with a throwaway preamble ("lemme peep that link") *before* the search call. Only the
        message items after the final non-message item are the answer; everything earlier is
        dropped.

        :param response: Response returned by the OpenAI Responses API.

        :returns Optional[str]: The reply text, if the response contained any.
        """
        last_non_message = max(
            (index for index, item in enumerate(response.output) if item.type != "message"),
            default=-1,
        )
        reply = "\n\n".join(
            part.text
            for item in response.output[last_non_message + 1 :]
            for part in item.content
            if part.type == "output_text"
        )
        return reply or None

    @staticmethod
    def _refusal(response) -> Optional[str]:
        """
        Report whether the model declined, rather than answered.

        A decline arrives either as a `refusal` content part or as a response cut short by the
        moderation filter — neither raises, so both are checked before the reply is read.

        :param response: Response returned by the OpenAI Responses API.

        :returns Optional[str]: Why the prompt was declined, if it was.
        """
        for item in response.output:
            if item.type != "message":
                continue
            for part in item.content:
                if part.type == "refusal":
                    return part.refusal or "unspecified"
        details = response.incomplete_details
        if response.status == "incomplete" and details and details.reason == "content_filter":
            return "content_filter"
        return None

    async def close(self) -> None:
        """
        Close the underlying `httpx` client owned by the OpenAI SDK.

        :returns: None
        """
        await self.client.close()
