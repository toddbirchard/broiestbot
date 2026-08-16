"""LLM conversational interactions."""

from typing import Optional

from anthropic import APIError, RateLimitError
from logger import LOGGER

from clients import claude
from clients.llm import LLMRefusalError


async def generate_llm_response(user_name: str, history, chat_message: str) -> Optional[str]:
    """
    Generate a response from the LLM based on the input prompt and chat history.

    :param str user_name: Username of the Chatango user who triggered the LLM response.
    :param list history: List of message objects representing the chat history.
    :param str chat_message: The message which tagged the bot, used to decide whether the LLM is
        allowed to read a link. Links elsewhere in the room's history are never fetched.

    :returns Optional[str]: HTML formatted response to be sent back to the chat
    """
    try:
        messages = claude.format_chat_history(history, format_type="messages")
        fetch_hosts = claude.fetchable_hosts(chat_message)
        if fetch_hosts:
            LOGGER.info(f"Allowing LLM to read links from {fetch_hosts} for @{user_name}")
        return await claude.generate_response(messages, fetch_hosts=fetch_hosts)
    except LLMRefusalError as e:
        LOGGER.warning(f"LLM declined to respond: {e}")
        return f"@{user_name} nah bro, i ain't touching that one."
    except RateLimitError as e:
        LOGGER.warning(f"LLM rate limit exceeded: {e}")
        return f"sry @{user_name}, brough is too cheap to pay for bert, lmao."
    except APIError as e:
        LOGGER.error(f"LLM API error: {e}")
        return f"@{user_name} i am trash, sry m8"
    except Exception as e:
        LOGGER.error(f"Error generating LLM response: {e}")
        return f"omg i died @{user_name}"
