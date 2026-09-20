"""Tests for `generate_llm_response`'s dubs-mode trigger short-circuit."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from broiestbot.commands.llm import generate_llm_response


def _run(coro):
    return asyncio.run(coro)


@patch("broiestbot.commands.llm.llm_client")
def test_activate_trigger_switches_mode_without_calling_the_llm(mock_client):
    """Activating dubs mode is deterministic: no `generate_response` call, no tokens spent."""
    mock_client.generate_response = AsyncMock()
    response = _run(generate_llm_response("todd", "room-a", [], "@bro activate dubs mode"))
    mock_client.activate_dubs_mode.assert_called_once_with("room-a")
    mock_client.deactivate_dubs_mode.assert_not_called()
    mock_client.generate_response.assert_not_called()
    assert "todd" in response
    assert "activated" in response


@patch("broiestbot.commands.llm.llm_client")
def test_deactivate_trigger_switches_mode_without_calling_the_llm(mock_client):
    """The reverse trigger is equally deterministic."""
    mock_client.generate_response = AsyncMock()
    response = _run(generate_llm_response("todd", "room-a", [], "@bro deactivate dubs mode"))
    mock_client.deactivate_dubs_mode.assert_called_once_with("room-a")
    mock_client.activate_dubs_mode.assert_not_called()
    mock_client.generate_response.assert_not_called()
    assert "todd" in response
    assert "deactivated" in response


@patch("broiestbot.commands.llm.llm_client")
def test_quoted_trigger_phrase_does_not_switch_mode(mock_client):
    """Quoting someone else's trigger phrase isn't a request to flip your own room's mode."""
    mock_client.format_chat_history = MagicMock(return_value=[])
    mock_client.fetchable_hosts = MagicMock(return_value=[])
    mock_client.generate_response = AsyncMock(return_value="<html>reply</html>")
    mock_client.RATE_LIMIT_ERROR = Exception
    mock_client.API_ERROR = Exception
    response = _run(
        generate_llm_response("todd", "room-a", [], "@broiestbot: `activate dubs mode` lmao what does that even mean")
    )
    mock_client.activate_dubs_mode.assert_not_called()
    mock_client.generate_response.assert_called_once()
    assert response == "<html>reply</html>"


@patch("broiestbot.commands.llm.llm_client")
def test_ordinary_prompt_still_reaches_the_llm(mock_client):
    """A message that isn't a mode trigger goes through the normal generation path."""
    mock_client.format_chat_history = MagicMock(return_value=[])
    mock_client.fetchable_hosts = MagicMock(return_value=[])
    mock_client.generate_response = AsyncMock(return_value="<html>reply</html>")
    mock_client.RATE_LIMIT_ERROR = Exception
    mock_client.API_ERROR = Exception
    response = _run(generate_llm_response("todd", "room-a", [], "@bro who won the derby"))
    mock_client.activate_dubs_mode.assert_not_called()
    mock_client.deactivate_dubs_mode.assert_not_called()
    mock_client.generate_response.assert_called_once_with(
        [], fetch_hosts=[], chat_message="@bro who won the derby", room_name="room-a"
    )
    assert response == "<html>reply</html>"
