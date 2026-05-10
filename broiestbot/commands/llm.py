"""LLM conversational interactions."""

from typing import Optional

from clients import claude
from anthropic import RateLimitError, APIError
from logger import LOGGER


def generate_llm_response(history) -> Optional[str]:
    """
    Generate a response from the LLM based on the input prompt and chat history.

    :param list history: List of message objects representing the chat history.

    :returns Optional[str]: HTML formatted response to be sent back to the chat
    """
    try:
        messages = claude.format_chat_history(history, format_type="messages")
        return claude.generate_response(messages)
    except RateLimitError as e:
        LOGGER.warning(f"LLM rate limit exceeded: {e}")
        return "Bro is too cheap to pay for bert, lmao."
    except APIError as e:
        LOGGER.error(f"LLM API error: {e}")
        return f"idk wtf happened: {e}"
    except Exception as e:
        LOGGER.error(f"Error generating LLM response: {e}")
        return "I died."
