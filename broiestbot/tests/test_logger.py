"""Test persisting of error logs."""

from os import mkdir, path

import pytest
from logger import LOGGER

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
