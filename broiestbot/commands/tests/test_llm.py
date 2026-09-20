"""Tests for `generate_llm_response`'s mode-trigger short-circuit."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from broiestbot.commands.llm import generate_llm_response
from config import LLM_MODE_EMOJIS, LLM_MODE_TRIGGERS


def _run(coro):
    return asyncio.run(coro)


def test_every_registered_mode_has_an_emoji():
    """A mode missing from `LLM_MODE_EMOJIS` would `KeyError` at activation time in chat."""
    assert set(LLM_MODE_TRIGGERS) == set(LLM_MODE_EMOJIS)


@patch("broiestbot.commands.llm.llm_client")
def test_activate_trigger_switches_mode_without_calling_the_llm(mock_client):
    """Activating a mode is deterministic: no `generate_response` call, no tokens spent."""
    mock_client.generate_response = AsyncMock()
    response = _run(generate_llm_response("todd", "room-a", [], "@bro activate dubs mode"))
    mock_client.activate_mode.assert_called_once_with("room-a", "dubs")
    mock_client.deactivate_mode.assert_not_called()
    mock_client.generate_response.assert_not_called()
    assert "todd" in response
    assert "activated" in response
    assert LLM_MODE_EMOJIS["dubs"] in response


@pytest.mark.parametrize("mode", list(LLM_MODE_TRIGGERS))
@patch("broiestbot.commands.llm.llm_client")
def test_activation_confirmation_carries_that_mode_s_own_emoji(mock_client, mode):
    """Each mode's activation reply carries its own emoji, not another mode's."""
    mock_client.generate_response = AsyncMock()
    response = _run(generate_llm_response("todd", "room-a", [], f"@bro activate {mode} mode"))
    assert LLM_MODE_EMOJIS[mode] in response
    other_emojis = [emoji for key, emoji in LLM_MODE_EMOJIS.items() if key != mode]
    assert not any(emoji in response for emoji in other_emojis)


@patch("broiestbot.commands.llm.llm_client")
def test_deactivate_trigger_switches_mode_without_calling_the_llm(mock_client):
    """The reverse trigger is equally deterministic."""
    mock_client.generate_response = AsyncMock()
    response = _run(generate_llm_response("todd", "room-a", [], "@bro deactivate dubs mode"))
    mock_client.deactivate_mode.assert_called_once_with("room-a", "dubs")
    mock_client.activate_mode.assert_not_called()
    mock_client.generate_response.assert_not_called()
    assert "todd" in response
    assert "deactivated" in response


@patch("broiestbot.commands.llm.llm_client")
def test_a_second_registered_mode_is_reachable_by_its_own_phrase(mock_client):
    """`cryptkeeper` isn't a special case — any registered mode is triggered the same way."""
    mock_client.generate_response = AsyncMock()
    response = _run(generate_llm_response("todd", "room-a", [], "@bro activate cryptkeeper mode"))
    mock_client.activate_mode.assert_called_once_with("room-a", "cryptkeeper")
    mock_client.generate_response.assert_not_called()
    assert "cryptkeeper" in response
    assert "activated" in response


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
    mock_client.activate_mode.assert_not_called()
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
    mock_client.activate_mode.assert_not_called()
    mock_client.deactivate_mode.assert_not_called()
    mock_client.generate_response.assert_called_once_with(
        [], fetch_hosts=[], chat_message="@bro who won the derby", room_name="room-a"
    )
    assert response == "<html>reply</html>"
