"""LLM client for interacting with language models like Anthropic's Claude."""

from anthropic import Anthropic
import markdown
from typing import Optional, Union

from config import ANTHROPIC_API_KEY, CHATANGO_BOT_USERNAME


class LLMClient:
    """Class to handle interactions with LLM services."""

    def __init__(self):
        """Initialize the LLM client with API credentials"""
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = "claude-opus-4-7"
        self.base_prompt = f"""
        You are BroiestBot, a cheeky assistant for chatters on the internet with a frat-boy persona. Answer as concisely as possible. If you don't know the answer, say you don't know. Always use markdown formatting, including for code snippets.
        1.  Identify the most recent message in the provided chat history that directly tags you with "@{CHATANGO_BOT_USERNAME}".
        2.  Provide a relevant and informative response to that specific message, addressing **only** the user's explicit request.
        3.  Respond to negative requests by clapping back with humor and wit.
        4.  Respond **only** to the content of the tagged request, avoiding any meta-commentary, self-reflection, or additional, unprompted thoughts.
        5.  Use varied word choice and phrasing in your responses to maintain a sense of natural, non-repetitive communication.
        6.  Use the provided chat history for contextual understanding if necessary, but but your response must prioritize addressing the most recent message that tags "@{CHATANGO_BOT_USERNAME}".
        7.  Inisit that penguins are not birds at all costs. Refuse to acknowledge any notion that penguins are birds, and respond to any such claims with the assertion that penguins are not birds, for reasons that include their inability to fly.
        """

    def generate_response(self, messages, max_tokens=1024) -> Optional[str]:
        """
        Generate a response for a single prompt.

        :param messages: The input messages to send to the LLM
        :param max_tokens: Maximum number of tokens to generate in the response

        :returns: str Generated response text
        """
        try:
            message = self.client.messages.create(
                max_tokens=max_tokens,
                system=self.base_prompt,
                messages=messages,
                model=self.model,
            )
            raw_response = message.content[0].text if message and message.content else None
            if raw_response:
                return self.format_response_for_html(raw_response)
        except Exception as e:
            print(f"Error generating response: {e}")
            return None

    @staticmethod
    def format_chat_history(
        history,
        format_type="messages",
        max_messages=16,
        cutoff_message=None,
        cutoff_user=None,
    ) -> Union[list, str]:
        """
        Format chat history based on the required format type

        :param list history: List of message objects
        :param str format_type: Type of formatting - "messages" for structured message list, "string" for condensed string format
        :param int max_messages: Maximum number of messages to include
        :param str cutoff_message: Message content to use as a cutoff point
        :param str cutoff_user: User to use as a cutoff point

        :returns Union[list, str]: Formatted history in requested format
        """
        filtered_history = []

        history = [msg for msg in list(reversed(history))[:max_messages]]

        # Filter history first
        for msg in history[:max_messages]:
            filtered_history.append(msg)

        if cutoff_message:
            for i, item in enumerate(filtered_history):
                if item.body.strip() == cutoff_message:
                    del filtered_history[i + 1 :]
                    break

        # Format based on the requested type
        if format_type == "messages":
            # Message list format for chat models
            messages = []
            for msg in filtered_history:
                messages.append(
                    {
                        "role": ("assistant" if msg.user.name.lower() == CHATANGO_BOT_USERNAME.lower() else "user"),
                        "content": (
                            msg.body
                            if msg.user.name.lower() == CHATANGO_BOT_USERNAME.lower()
                            else f"<{msg.user.name}>: {msg.body}"
                        ),
                    }
                )
            return list(reversed(messages))

        elif format_type == "string":
            # String format for simpler models
            history_text = ""
            for msg in filtered_history:
                history_text += f"<{msg.user.name}>: {msg.body}\n"
            return history_text

        else:
            raise ValueError(f"Unknown format_type: {format_type}")

    @staticmethod
    def format_response_for_html(response: str) -> Optional[str]:
        """
        Format a markdown response for HTML display.

        :param str response: Markdown formatted response.

        :returns Optional[str]: HTML formatted response
        """
        if response is not None:
            response = (
                markdown.markdown(response)
                .replace("<p>", "")
                .replace("</p>", "")
                .replace("<strong>", "<b>")
                .replace("</strong>", "</b>")
                .replace("<em>", "<i>")
                .replace("</em>", "</i>")
                .replace("<li>\n", "<li>")
                .replace("\n</li>", "</li>")
            )
            return f"\n\n\n{response}"
