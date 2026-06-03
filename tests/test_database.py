"""
Integration tests for database persistence and query operations.

These tests hit the real database. They use a TEST_USERNAME_PREFIX prefix so
conftest.cleanup_test_rows can delete them after every test.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from broiestbot.bot import _db_fetch_command, _db_fetch_phrase
from broiestbot.data.chats import persist_chat_logs
from broiestbot.data.users import persist_user_data
from database import Session, init_db
from database.models import Chat, ChatangoUser

from tests.conftest import TEST_USERNAME_PREFIX

TEST_ROOM = "__pytest_room__"
BOT_USERNAME = "broiestbro"

# Minimal geo response that satisfies all attribute lookups in persist_user_data.
MOCK_GEO_DATA = {
    "city": "Test City",
    "region": "Test Region",
    "country_name": "Testland",
    "company": "Test ISP",
    "latitude": 0.0,
    "longitude": 0.0,
    "postal": "00000",
    "emoji_flag": "\U0001f3f3",
    "languages": [{"name": "English"}],
    "currency": {"name": "Dollar", "symbol": "$"},
    "threat": {"is_tor": False, "is_proxy": False, "is_known_attacker": False, "is_threat": False},
    "time_zone": {"name": "UTC", "abbr": "UTC", "offset": 0, "is_dst": False, "current_time": None},
    "carrier": {"name": None, "mnc": None, "mcc": None},
    "asn": {"asn": None, "name": None, "domain": None, "route": None, "type": None},
}


# ---------------------------------------------------------------------------
# persist_chat_logs
# ---------------------------------------------------------------------------


class TestPersistChatLogs:
    def test_inserts_row(self):
        user = f"{TEST_USERNAME_PREFIX}_chat1"
        asyncio.run(persist_chat_logs(user, TEST_ROOM, "hello world", BOT_USERNAME))
        with Session() as db:
            row = db.query(Chat).filter(Chat.username == user, Chat.room == TEST_ROOM).first()
        assert row is not None
        assert row.message == "hello world"

    def test_skips_when_bot_username_not_in_allowlist(self):
        user = f"{TEST_USERNAME_PREFIX}_skip"
        asyncio.run(persist_chat_logs(user, TEST_ROOM, "should not persist", "someotherbot"))
        with Session() as db:
            row = db.query(Chat).filter(Chat.username == user).first()
        assert row is None

    def test_session_recovers_after_integrity_error(self):
        """Two calls with duplicate data both complete without raising."""
        user = f"{TEST_USERNAME_PREFIX}_dup"
        asyncio.run(persist_chat_logs(user, TEST_ROOM, "msg", BOT_USERNAME))
        asyncio.run(persist_chat_logs(user, TEST_ROOM, "msg2", BOT_USERNAME))
        with Session() as db:
            count = db.query(Chat).filter(Chat.username == user).count()
        assert count >= 1

    def test_concurrent_inserts_all_succeed(self):
        async def run():
            tasks = [
                persist_chat_logs(
                    f"{TEST_USERNAME_PREFIX}_concurrent{i}",
                    TEST_ROOM,
                    f"concurrent message {i}",
                    BOT_USERNAME,
                )
                for i in range(20)
            ]
            return await asyncio.gather(*tasks, return_exceptions=True)

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

    def test_skips_when_persist_chat_data_disabled(self):
        """PERSIST_CHAT_DATA=False must prevent any row being written."""
        user = f"{TEST_USERNAME_PREFIX}_nocfg"
        with patch("broiestbot.data.chats.PERSIST_CHAT_DATA", False):
            asyncio.run(persist_chat_logs(user, TEST_ROOM, "should not persist", BOT_USERNAME))
        with Session() as db:
            row = db.query(Chat).filter(Chat.username == user).first()
        assert row is None

    def test_does_not_raise_on_db_error(self):
        """persist_chat_logs must swallow all exceptions — the bot should never crash."""
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.add.side_effect = SQLAlchemyError("simulated failure")
        with patch("broiestbot.data.chats.async_session") as mock_session_cls:
            mock_session_cls.begin.return_value = mock_ctx
            asyncio.run(persist_chat_logs(f"{TEST_USERNAME_PREFIX}_err", TEST_ROOM, "msg", BOT_USERNAME))

    def test_recovers_after_simulated_failure(self):
        """A failed first call must not prevent subsequent real insertions from succeeding."""
        user = f"{TEST_USERNAME_PREFIX}_recovery"

        failing_ctx = AsyncMock()
        failing_ctx.__aenter__ = AsyncMock(return_value=failing_ctx)
        failing_ctx.__aexit__ = AsyncMock(return_value=False)
        failing_ctx.add.side_effect = SQLAlchemyError("simulated transient error")
        with patch("broiestbot.data.chats.async_session") as mock_session_cls:
            mock_session_cls.begin.return_value = failing_ctx
            asyncio.run(persist_chat_logs(user, TEST_ROOM, "will fail", BOT_USERNAME))

        asyncio.run(persist_chat_logs(user, TEST_ROOM, "will succeed", BOT_USERNAME))

        with Session() as db:
            row = db.query(Chat).filter(Chat.username == user, Chat.message == "will succeed").first()
        assert row is not None, "Second call must insert a row after the first call failed"


# ---------------------------------------------------------------------------
# _db_fetch_command / _db_fetch_phrase
# ---------------------------------------------------------------------------


class TestDbFetch:
    def test_fetch_command_returns_object_with_accessible_attrs(self):
        cmd = asyncio.run(_db_fetch_command(":@"))
        assert cmd is not None
        assert cmd.command == ":@"
        assert cmd.type == "basic"
        assert cmd.response is not None

    def test_fetch_command_returns_none_for_missing(self):
        result = asyncio.run(_db_fetch_command("__nonexistent_pytest_cmd__"))
        assert result is None

    def test_fetch_phrase_returns_object_with_accessible_attrs(self):
        phrase = asyncio.run(_db_fetch_phrase("bro?"))
        assert phrase is not None
        assert phrase.phrase == "bro?"
        assert phrase.response is not None

    def test_fetch_phrase_returns_none_for_missing(self):
        result = asyncio.run(_db_fetch_phrase("__nonexistent_pytest_phrase__"))
        assert result is None

    def test_repeated_fetches_use_independent_sessions(self):
        """Multiple concurrent fetches must all succeed with no session state leakage."""

        async def run():
            return await asyncio.gather(*[_db_fetch_command(":@") for _ in range(10)])

        cmds = asyncio.run(run())
        assert all(c is not None for c in cmds)
        assert all(c.type == "basic" for c in cmds)


# ---------------------------------------------------------------------------
# Full on_message DB path
# ---------------------------------------------------------------------------


class TestOnMessageDbPath:
    def test_sequential_persist_user_then_chat(self, mock_user, mock_message):
        """Mirrors the exact sequential awaits in on_message."""

        async def run():
            await persist_user_data(TEST_ROOM, mock_user, mock_message, BOT_USERNAME)
            await persist_chat_logs(mock_user.name, TEST_ROOM, mock_message.body, BOT_USERNAME)

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
        asyncio.run(persist_user_data(TEST_ROOM, mock_user, mock_message, BOT_USERNAME))

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
            await persist_chat_logs(user.name, TEST_ROOM, msg.body, BOT_USERNAME)

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


# ---------------------------------------------------------------------------
# persist_user_data
# ---------------------------------------------------------------------------


class TestPersistUserData:
    def test_skips_when_bot_username_not_in_allowlist(self, mock_user, mock_message):
        asyncio.run(persist_user_data(TEST_ROOM, mock_user, mock_message, "someotherbot"))
        with Session() as db:
            row = db.query(ChatangoUser).filter(ChatangoUser.username == mock_user.name.lower()).first()
        assert row is None

    def test_skips_when_persist_user_data_disabled(self, mock_user, mock_message):
        with patch("broiestbot.data.users.PERSIST_USER_DATA", False):
            asyncio.run(persist_user_data(TEST_ROOM, mock_user, mock_message, BOT_USERNAME))
        with Session() as db:
            row = db.query(ChatangoUser).filter(ChatangoUser.username == mock_user.name.lower()).first()
        assert row is None

    def test_skips_geo_when_existing_user_found(self, mock_user, mock_message):
        """If the user is already in the DB, geo lookup must not be called."""
        with Session() as db:
            db.add(
                ChatangoUser(
                    username=mock_user.name.lower(),
                    chatango_room=TEST_ROOM,
                    ip=mock_message.ip,
                )
            )
            db.commit()
        with patch("broiestbot.data.users.geo") as mock_geo:
            asyncio.run(persist_user_data(TEST_ROOM, mock_user, mock_message, BOT_USERNAME))
            mock_geo.lookup_user_by_ip.assert_not_called()

    def test_skips_insert_when_geo_returns_none(self, mock_user, mock_message):
        with patch("broiestbot.data.users.geo") as mock_geo:
            mock_geo.lookup_user_by_ip = MagicMock(return_value=None)
            asyncio.run(persist_user_data(TEST_ROOM, mock_user, mock_message, BOT_USERNAME))
        with Session() as db:
            row = db.query(ChatangoUser).filter(ChatangoUser.username == mock_user.name.lower()).first()
        assert row is None

    def test_inserts_user_with_geo_data(self, mock_user, mock_message):
        with patch("broiestbot.data.users.geo") as mock_geo:
            mock_geo.lookup_user_by_ip = MagicMock(return_value=MOCK_GEO_DATA)
            asyncio.run(persist_user_data(TEST_ROOM, mock_user, mock_message, BOT_USERNAME))
        with Session() as db:
            row = (
                db.query(ChatangoUser)
                .filter(
                    ChatangoUser.username == mock_user.name.lower(),
                    ChatangoUser.chatango_room == TEST_ROOM,
                )
                .first()
            )
        assert row is not None
        assert row.city == "Test City"
        assert row.country_name == "Testland"
        assert row.ip == mock_message.ip

    def test_normalises_anon_username(self, mock_message):
        """Anon users must have a timestamp suffix appended to their name."""
        anon_user = MagicMock()
        anon_user.name = f"{TEST_USERNAME_PREFIX}_!anon1234"
        with patch("broiestbot.data.users.geo") as mock_geo:
            mock_geo.lookup_user_by_ip = MagicMock(return_value=MOCK_GEO_DATA)
            asyncio.run(persist_user_data(TEST_ROOM, anon_user, mock_message, BOT_USERNAME))
        with Session() as db:
            rows = db.query(ChatangoUser).filter(ChatangoUser.username.like(f"{TEST_USERNAME_PREFIX}_anon1234-%")).all()
        assert len(rows) == 1
        assert rows[0].username.startswith(f"{TEST_USERNAME_PREFIX}_anon1234-")

    def test_does_not_raise_on_integrity_error(self, mock_user, mock_message):
        """IntegrityError from the DB layer must be caught silently."""
        failing_ctx = AsyncMock()
        failing_ctx.add.side_effect = IntegrityError("stmt", {}, Exception("orig"))
        with patch("broiestbot.data.users._check_existing_user", new=AsyncMock(return_value=None)):
            with patch("broiestbot.data.users.geo") as mock_geo:
                mock_geo.lookup_user_by_ip = MagicMock(return_value=MOCK_GEO_DATA)
                with patch("broiestbot.data.users.async_session") as mock_session:
                    mock_session.begin.return_value = failing_ctx
                    asyncio.run(persist_user_data(TEST_ROOM, mock_user, mock_message, BOT_USERNAME))

    def test_does_not_raise_on_sqlalchemy_error(self, mock_user, mock_message):
        """Any SQLAlchemyError during the insert must be caught and not re-raised."""
        failing_ctx = AsyncMock()
        failing_ctx.add.side_effect = SQLAlchemyError("simulated DB failure")
        with patch("broiestbot.data.users._check_existing_user", new=AsyncMock(return_value=None)):
            with patch("broiestbot.data.users.geo") as mock_geo:
                mock_geo.lookup_user_by_ip = MagicMock(return_value=MOCK_GEO_DATA)
                with patch("broiestbot.data.users.async_session") as mock_session:
                    mock_session.begin.return_value = failing_ctx
                    asyncio.run(persist_user_data(TEST_ROOM, mock_user, mock_message, BOT_USERNAME))


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------


class TestInitDb:
    def test_init_db_runs_without_error(self):
        """init_db must complete without raising even when tables already exist."""
        asyncio.run(init_db())
