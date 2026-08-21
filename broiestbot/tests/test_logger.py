"""Test persisting & serialization of logs."""

import json
from datetime import datetime, timedelta
from os import mkdir, path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from logger import LOGGER, json_formatter

from config import BASE_DIR, ENVIRONMENT


@pytest.fixture
def log_local_directory() -> str:
    """Local directory where error logs are saved."""
    return f"{BASE_DIR}/logs/"


@pytest.fixture
def info_log_filepath() -> str:
    """Local filepath to INFO `.log` file."""
    return f"{BASE_DIR}/logs/info.log"


@pytest.fixture
def json_log_filepath() -> str:
    """Local filepath to JSON log file."""
    return f"{BASE_DIR}/logs/info.json"


def test_sms_logger(log_local_directory: str, info_log_filepath: str, json_log_filepath: str):
    """
    Create local directory to store logs in development.

    :param str log_local_directory: Local directory where `INFO` logs are saved.
    :param str info_log_filepath: Local filepath to `INFO` log.
    :param str json_log_filepath: Local filepath to JSON log.

    :returns: str
    """
    log_creation_helper(log_local_directory)
    LOGGER.error("This is a TEST_ERROR log from Broiestbot")
    assert path.exists(log_local_directory)
    assert path.isfile(info_log_filepath)
    with open(info_log_filepath, "r", encoding="utf-8") as f:
        last_line = f.readlines()[-1]
        assert "TEST_ERROR" in last_line
    with open(json_log_filepath, "r", encoding="utf-8") as f:
        last_line = f.readlines()[-1]
        assert "TEST_ERROR" in last_line


def log_creation_helper(log_local_directory: str):
    """
    Create local directory to store logs in development.

    :param str log_local_directory: Local directory where error logs are saved.

    :returns: str
    """
    if ENVIRONMENT == "development":
        if path.exists(log_local_directory) is False:
            mkdir(f"{BASE_DIR}/logs/")


@pytest.fixture
def log_record_factory():
    """Build a minimal Loguru-style record for a given level & message."""

    def _factory(level: str, message: str) -> dict:
        return {
            "time": datetime(2026, 8, 21, 9, 30, 0),
            "elapsed": timedelta(seconds=3),
            "level": SimpleNamespace(name=level),
            "message": message,
            "extra": {},
        }

    return _factory


@pytest.mark.parametrize(
    "level,message",
    [
        ("INFO", "Starting in dev mode..."),
        ("INFO", "Checking for Daddy anons: username=broiestbro ip=1.2.3.4"),
        ("INFO", "[room] [user] [1.2.3.4]: !weather nyc"),
        ("INFO", "[room] [user] [1.2.3.4] no colon separator"),
        ("INFO", "[room] [user] [no IP address]: hello"),
        ("SUCCESS", "Joined Chatango room 420blazeitxd."),
        ("SUCCESS", "[room] [user]: Successfully connected to room"),
        ("WARNING", "[room] [user]: user was muted"),
        ("TRACE", "raw trace line"),
        ("DEBUG", "raw debug line"),
    ],
)
def test_json_formatter_always_emits_json(log_record_factory, level: str, message: str):
    """Every log level serializes to valid JSON rather than a bare `None`."""
    record = log_record_factory(level, message)
    assert json_formatter(record) == "{extra[serialized]},\n"
    log = json.loads(record["extra"]["serialized"])
    assert log["level"] == level
    assert log["time"] == "08/21/2026, 09:30:00"
    assert log["message"]


def test_json_formatter_parses_chat_metadata(log_record_factory):
    """Chat messages are split into room/user/ip fields, newlines flattened."""
    record = log_record_factory("INFO", "[420blazeitxd] [broiestbro] [1.2.3.4]: multi\nline: message")
    json_formatter(record)
    log = json.loads(record["extra"]["serialized"])
    assert log["room"] == "420blazeitxd"
    assert log["user"] == "broiestbro"
    assert log["ip"] == "1.2.3.4"
    assert log["message"] == "multi\tline: message"


@pytest.mark.parametrize(
    "message",
    [
        "[420blazeitxd] [broiestbro]: hello",
        "[420blazeitxd] [broiestbro] [no IP address]: hello",
    ],
)
def test_json_formatter_omits_ip_when_bot_is_not_moderator(log_record_factory, message: str):
    """Chatango only discloses IPs to mods; room & user are still parsed without one."""
    record = log_record_factory("INFO", message)
    json_formatter(record)
    log = json.loads(record["extra"]["serialized"])
    assert log["room"] == "420blazeitxd"
    assert log["user"] == "broiestbro"
    assert log["message"] == "hello"
    assert "ip" not in log


def test_json_formatter_handles_empty_message(log_record_factory):
    """An empty error message still produces a parseable record."""
    record = log_record_factory("ERROR", "")
    with patch("logger.sms_error_handler"):
        json_formatter(record)
    log = json.loads(record["extra"]["serialized"])
    assert log["level"] == "ERROR"
    assert log["message"] == "(No message provided)"


def test_json_formatter_leaves_record_unmutated(log_record_factory):
    """The record is shared across sinks, so the JSON sink must not rewrite its fields."""
    record = log_record_factory("INFO", "Starting in dev mode...")
    json_formatter(record)
    assert isinstance(record["time"], datetime)
    assert isinstance(record["elapsed"], timedelta)
