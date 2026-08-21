"""Custom logger and error notifications."""

import json
import re
from datetime import datetime
from sys import stdout

from loguru import logger

from clients import sms
from config import BASE_DIR, ENVIRONMENT, TWILIO_BRO_PHONE_NUMBER, TWILIO_SENDER_PHONE

CHAT_LOG_PATTERN = re.compile(
    r"^\[(?P<room>[^]]*)] \[(?P<user>[^]]*)](?: \[(?P<ip>[^]]*)])?: (?P<body>.*)",
    re.DOTALL,
)

# `bot.py` logs this placeholder in rooms where the bot isn't a mod (Chatango only discloses IPs to mods).
MISSING_IP_PLACEHOLDER = "no IP address"


def json_formatter(record: dict) -> str:
    """
    Serialize a log record as a single JSON object.

    :param dict record: Log object containing log metadata & message.

    :returns: str
    """
    if isinstance(record, (str, bool)):
        return json.dumps(construct_json_from_corrupted_log(record))

    log = {
        "time": record["time"].strftime("%m/%d/%Y, %H:%M:%S"),
        "level": record["level"].name,
        "message": record.get("message") or "(No message provided)",
    }
    if log["level"] in ("ERROR", "CRITICAL"):
        serialized = serialize_error(log)
        sms_error_handler(log)
    else:
        serialized = serialize_chat_message(log)
    record["extra"]["serialized"] = serialized
    return "{extra[serialized]},\n"


def serialize_chat_message(log: dict) -> str:
    """
    Construct JSON log record for a message logged from within a Chatango room.

    Falls back to a plain record when the log isn't a chat message (bot lifecycle
    events, moderation checks, etc.); such logs are still valid JSON.

    :param dict log: Dictionary containing logged message with metadata.

    :returns: str
    """
    try:
        chat_data = CHAT_LOG_PATTERN.match(log["message"])
        if chat_data is None:
            return serialize_default(log)
        subset = {
            "time": log["time"],
            "message": chat_data["body"].replace("\n", "\t"),
            "level": log["level"],
            "room": chat_data["room"],
            "user": chat_data["user"],
        }
        if chat_data["ip"] and chat_data["ip"] != MISSING_IP_PLACEHOLDER:
            subset["ip"] = chat_data["ip"]
        return json.dumps(subset)
    except Exception as e:
        return serialize_default(log, error=f"Logging error occurred: {str(e)}")


def serialize_error(log: dict) -> str:
    """
    Construct error log record.

    :param dict log: Dictionary containing logged message with metadata.

    :returns: str
    """
    return serialize_default(log)


def serialize_default(log: dict, error: str = None) -> str:
    """
    Construct a bare log record out of a message which has no additional metadata.

    :param dict log: Dictionary containing logged message with metadata.
    :param str error: Optional error encountered while serializing the log.

    :returns: str
    """
    subset = {
        "time": log["time"],
        "level": log["level"],
        "message": log["message"],
    }
    if error:
        subset["error"] = error
    return json.dumps(subset)


def construct_json_from_corrupted_log(log: str) -> dict:
    """
    Create JSON log record from corrupt string.

    :param str log: Corrupt log string.

    :returns: str
    """
    return {
        "time": datetime.strftime(datetime.now(), "%m/%d/%Y, %H:%M:%S"),
        "level": "ERROR",
        "message": log,
    }


def sms_error_handler(log: dict) -> None:
    """
    Trigger error log SMS notification.

    :param dict log: Log object containing log metadata & message.

    :returns: None
    """
    try:
        sms.messages.create(
            body=f'BROBOT ERROR: {log["time"]} | {log["message"]}',
            from_=TWILIO_SENDER_PHONE,
            to=TWILIO_BRO_PHONE_NUMBER,
        )
    except Exception as e:
        logger.bind(sms_notification=False).warning(f"Failed to send SMS notification for error log: {e}")


def log_formatter(record: dict) -> str:
    """
    Formatter for .log records

    :param dict record: Key/value object containing log message & metadata.

    :returns: str
    """
    if record["level"].name == "TRACE":
        return "<fg #5278a3>{time:MM-DD-YYYY HH:mm:ss}</fg #5278a3> | <fg #d2eaff>{level}</fg #d2eaff>: <light-white>{message}</light-white>\n"
    if record["level"].name == "INFO":
        return "<fg #5278a3>{time:MM-DD-YYYY HH:mm:ss}</fg #5278a3> | <fg #98bedf>{level}</fg #98bedf>: <light-white>{message}</light-white>\n"
    if record["level"].name == "WARNING":
        return "<fg #5278a3>{time:MM-DD-YYYY HH:mm:ss}</fg #5278a3> |  <fg #b09057>{level}</fg #b09057>: <light-white>{message}</light-white>\n"
    if record["level"].name == "SUCCESS":
        return "<fg #5278a3>{time:MM-DD-YYYY HH:mm:ss}</fg #5278a3> | <fg #6dac77>{level}</fg #6dac77>: <light-white>{message}</light-white>\n"
    if record["level"].name == "ERROR":
        return "<fg #5278a3>{time:MM-DD-YYYY HH:mm:ss}</fg #5278a3> | <fg #a35252>{level}</fg #a35252>: <light-white>{message}</light-white>\n"
    if record["level"].name == "CRITICAL":
        return "<fg #5278a3>{time:MM-DD-YYYY HH:mm:ss}</fg #5278a3> | <fg #521010>{level}</fg #521010>: <light-white>{message}</light-white>\n"
    return "<fg #5278a3>{time:MM-DD-YYYY HH:mm:ss}</fg #5278a3> | <fg #98bedf>{level}</fg #98bedf>: <light-white>{message}</light-white>\n"


def create_logger():
    """Configure custom logger."""
    logger.remove()
    logger.add(stdout, colorize=True, catch=True, format=log_formatter, level="TRACE")
    if ENVIRONMENT == "production":
        # Human-readable info logs
        logger.add(
            "/var/log/broiestbot/info.log",
            colorize=True,
            catch=True,
            level="TRACE",
            format=log_formatter,
            rotation="5 MB",
            compression="zip",
        )
        # Human-readable error logs
        logger.add(
            "/var/log/broiestbot/error.log",
            colorize=True,
            catch=True,
            level="ERROR",
            format=log_formatter,
            rotation="5 MB",
            compression="zip",
        )
        # Datadog JSON logs
        logger.add(
            "/var/log/broiestbot/info.json",
            format=json_formatter,
            rotation="5 MB",
            compression="zip",
            level="TRACE",
        )
    elif ENVIRONMENT == "development":
        # Human-readable info logs
        logger.add(
            f"{BASE_DIR}/logs/info.log",
            colorize=True,
            catch=True,
            level="TRACE",
            format=log_formatter,
            rotation="5 MB",
            compression="zip",
        )
        # Human-readable error logs
        logger.add(
            f"{BASE_DIR}/logs/error.log",
            colorize=True,
            catch=True,
            level="ERROR",
            format=log_formatter,
            rotation="5 MB",
            compression="zip",
        )
        # Datadog JSON logs
        logger.add(
            f"{BASE_DIR}/logs/info.json",
            format=json_formatter,
            rotation="5 MB",
            compression="zip",
            level="TRACE",
        )
    return logger


LOGGER = create_logger()
