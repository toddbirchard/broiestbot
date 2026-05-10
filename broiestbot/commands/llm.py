"""LLM conversational interactions."""

from typing import Optional

from clients import claude
from anthropic import RateLimitError, APIError
from logger import LOGGER


def generate_llm_response(user_name: str, history) -> Optional[str]:
    """
    Generate a response from the LLM based on the input prompt and chat history.

    :param str user_name: Username of the Chatango user who triggered the LLM response.
    :param list history: List of message objects representing the chat history.

    :returns Optional[str]: HTML formatted response to be sent back to the chat
    """
    try:
        messages = claude.format_chat_history(history, format_type="messages")
        return claude.generate_response(messages)
    except RateLimitError as e:
        LOGGER.warning(f"LLM rate limit exceeded: {e}")
        return f"sry @{user_name}, brough is too cheap to pay for bert, lmao."
    except APIError as e:
        LOGGER.error(f"LLM API error: {e}")
        return f"@{user_name} i am trash, sry m8"
    except Exception as e:
        LOGGER.error(f"Error generating LLM response: {e}")
        return f"omg i died @{user_name}"
