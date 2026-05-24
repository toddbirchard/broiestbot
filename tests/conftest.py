"""Shared fixtures for broiestbot tests."""

import asyncio
from unittest.mock import MagicMock

import pytest

from database import Session
from database.models import Chat, ChatangoUser

TEST_USERNAME_PREFIX = "__pytest__"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def cleanup_test_rows():
    """Remove any test rows written during a test."""
    yield
    with Session() as db:
        db.query(Chat).filter(Chat.username.like(f"{TEST_USERNAME_PREFIX}%")).delete()
        db.query(ChatangoUser).filter(ChatangoUser.username.like(f"{TEST_USERNAME_PREFIX}%")).delete()
        db.commit()


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.name = f"{TEST_USERNAME_PREFIX}user1"
    return user


@pytest.fixture
def mock_message(mock_user):
    message = MagicMock()
    message.ip = "203.0.113.1"  # TEST-NET-3, documentation-only range
    message.body = "test message"
    message.user = mock_user
    return message
