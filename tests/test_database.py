"""
Integration tests for database persistence and query operations.

These tests hit the real database. They use a TEST_USERNAME_PREFIX prefix so
conftest.cleanup_test_rows can delete them after every test.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from broiestbot.bot import _db_fetch_command, _db_fetch_phrase
from broiestbot.data.chats import persist_chat_logs
from broiestbot.data.users import persist_user_data
from database import Session
from database.models import Chat, ChatangoUser

from tests.conftest import TEST_USERNAME_PREFIX

TEST_ROOM = "__pytest_room__"
BOT_USERNAME = "broiestbro"


# ---------------------------------------------------------------------------
# persist_chat_logs
# ---------------------------------------------------------------------------


class TestPersistChatLogs:
    def test_inserts_row(self):
        user = f"{TEST_USERNAME_PREFIX}_chat1"
        persist_chat_logs(user, TEST_ROOM, "hello world", BOT_USERNAME)
        with Session() as db:
            row = db.query(Chat).filter(Chat.username == user, Chat.room == TEST_ROOM).first()
        assert row is not None
        assert row.message == "hello world"

    def test_skips_when_bot_username_not_in_allowlist(self):
        user = f"{TEST_USERNAME_PREFIX}_skip"
        persist_chat_logs(user, TEST_ROOM, "should not persist", "someotherbot")
        with Session() as db:
            row = db.query(Chat).filter(Chat.username == user).first()
        assert row is None

    def test_session_recovers_after_integrity_error(self):
        """Two calls with duplicate data both complete without raising."""
        user = f"{TEST_USERNAME_PREFIX}_dup"
        persist_chat_logs(user, TEST_ROOM, "msg", BOT_USERNAME)
        # Second call with identical data — may hit unique constraints on some rows
        persist_chat_logs(user, TEST_ROOM, "msg2", BOT_USERNAME)
        with Session() as db:
            count = db.query(Chat).filter(Chat.username == user).count()
        assert count >= 1

    def test_concurrent_inserts_all_succeed(self):
        async def run():
            tasks = [
                asyncio.to_thread(
                    persist_chat_logs,
                    f"{TEST_USERNAME_PREFIX}_concurrent{i}",
                    TEST_ROOM,
                    f"concurrent message {i}",
                    BOT_USERNAME,
                )
                for i in range(20)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results

        results = asyncio.run(run())
        failures = [r for r in results if isinstance(r, Exception)]
        assert failures == [], f"Concurrent inserts had failures: {failures}"

        with Session() as db:
            count = (
                db.query(Chat)
                .filter(
                    Chat.username.like(f"{TEST_USERNAME_PREFIX}_concurrent%"),
                    Chat.room == TEST_ROOM,
                )
                .count()
            )
        assert count == 20

    def test_does_not_raise_on_db_error(self):
        """persist_chat_logs must swallow all exceptions — the bot should never crash."""
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        ctx.add.side_effect = SQLAlchemyError("simulated failure")
        with patch("broiestbot.data.chats.Session") as mock_session_cls:
            mock_session_cls.begin.return_value = ctx
            # Must not raise
            persist_chat_logs(f"{TEST_USERNAME_PREFIX}_err", TEST_ROOM, "msg", BOT_USERNAME)

    def test_recovers_after_simulated_failure(self):
        """A failed first call must not prevent subsequent real insertions from succeeding.

        With Session.begin(), rollback is handled automatically by the context manager.
        We verify that the error path is silent and the next real call succeeds.
        """
        user = f"{TEST_USERNAME_PREFIX}_recovery"

        # First call: simulate Session.begin() context manager raising on add()
        failing_ctx = MagicMock()
        failing_ctx.__enter__ = MagicMock(return_value=failing_ctx)
        failing_ctx.__exit__ = MagicMock(return_value=False)
        failing_ctx.add.side_effect = SQLAlchemyError("simulated transient error")
        with patch("broiestbot.data.chats.Session") as mock_session_cls:
            mock_session_cls.begin.return_value = failing_ctx
            persist_chat_logs(user, TEST_ROOM, "will fail", BOT_USERNAME)
            # No exception must propagate

        # Second call uses the real session — must insert successfully
        persist_chat_logs(user, TEST_ROOM, "will succeed", BOT_USERNAME)

        with Session() as db:
            row = db.query(Chat).filter(Chat.username == user, Chat.message == "will succeed").first()
        assert row is not None, "Second call must insert a row after the first call failed"


# ---------------------------------------------------------------------------
# _db_fetch_command / _db_fetch_phrase
# ---------------------------------------------------------------------------


class TestDbFetch:
    def test_fetch_command_returns_object_with_accessible_attrs(self):
        async def run():
            cmd = await asyncio.to_thread(_db_fetch_command, ":@")
            return cmd

        cmd = asyncio.run(run())
        # Session is closed at this point — attributes must still be accessible
        assert cmd is not None
        assert cmd.command == ":@"
        assert cmd.type == "basic"
        assert cmd.response is not None

    def test_fetch_command_returns_none_for_missing(self):
        async def run():
            return await asyncio.to_thread(_db_fetch_command, "__nonexistent_pytest_cmd__")

        result = asyncio.run(run())
        assert result is None

    def test_fetch_phrase_returns_object_with_accessible_attrs(self):
        async def run():
            return await asyncio.to_thread(_db_fetch_phrase, "bro?")

        phrase = asyncio.run(run())
        assert phrase is not None
        assert phrase.phrase == "bro?"
        assert phrase.response is not None

    def test_fetch_phrase_returns_none_for_missing(self):
        async def run():
            return await asyncio.to_thread(_db_fetch_phrase, "__nonexistent_pytest_phrase__")

        result = asyncio.run(run())
        assert result is None

    def test_repeated_fetches_use_independent_sessions(self):
        """Multiple sequential fetches must all succeed with no session state leakage."""

        async def run():
            results = []
            for _ in range(10):
                cmd = await asyncio.to_thread(_db_fetch_command, ":@")
                results.append(cmd)
            return results

        cmds = asyncio.run(run())
        assert all(c is not None for c in cmds)
        assert all(c.type == "basic" for c in cmds)


# ---------------------------------------------------------------------------
# Full on_message DB path (asyncio.to_thread)
# ---------------------------------------------------------------------------


class TestOnMessageDbPath:
    def test_sequential_persist_user_then_chat(self, mock_user, mock_message):
        """Mirrors the exact sequential awaits in on_message."""

        async def run():
            await asyncio.to_thread(persist_user_data, TEST_ROOM, mock_user, mock_message, BOT_USERNAME)
            await asyncio.to_thread(
                persist_chat_logs,
                mock_user.name,
                TEST_ROOM,
                mock_message.body,
                BOT_USERNAME,
            )

        asyncio.run(run())

        with Session() as db:
            chat_row = (
                db.query(Chat)
                .filter(
                    Chat.username == mock_user.name,
                    Chat.room == TEST_ROOM,
                )
                .first()
            )
        assert chat_row is not None
        assert chat_row.message == mock_message.body

    def test_no_persist_when_ip_missing(self, mock_user, mock_message):
        mock_message.ip = None

        async def run():
            await asyncio.to_thread(persist_user_data, TEST_ROOM, mock_user, mock_message, BOT_USERNAME)

        asyncio.run(run())

        with Session() as db:
            row = db.query(ChatangoUser).filter(ChatangoUser.username == mock_user.name).first()
        assert row is None

    def test_session_isolation_across_concurrent_messages(self):
        """20 concurrent on_message DB paths must not interfere with each other."""

        async def one_message(i):
            user = MagicMock()
            user.name = f"{TEST_USERNAME_PREFIX}_iso{i}"
            msg = MagicMock()
            msg.ip = None  # skip user persist
            msg.body = f"isolation test {i}"
            msg.user = user
            await asyncio.to_thread(persist_chat_logs, user.name, TEST_ROOM, msg.body, BOT_USERNAME)

        async def run():
            await asyncio.gather(*[one_message(i) for i in range(20)])

        asyncio.run(run())

        with Session() as db:
            count = (
                db.query(Chat)
                .filter(
                    Chat.username.like(f"{TEST_USERNAME_PREFIX}_iso%"),
                    Chat.room == TEST_ROOM,
                )
                .count()
            )
        assert count == 20
