"""Custom logger and error notifications."""

import json
import re
from datetime import datetime
from sys import stdout

from loguru import logger

from clients import sms
from config import BASE_DIR, ENVIRONMENT, TWILIO_BRO_PHONE_NUMBER, TWILIO_SENDER_PHONE


def json_formatter(record: dict) -> str:
    """
    Format info message logs.

    :param dict record: Log object containing log metadata & message.

    :returns: str
    """
    if isinstance(record, (str, bool)):
        return construct_json_from_corrupted_log(record)

    record["time"] = record["time"].strftime("%m/%d/%Y, %H:%M:%S")
    record["elapsed"] = record["elapsed"].total_seconds()

    def serialize_as_admin(log: dict) -> str:
        """
        Construct JSON info log record where user is room admin.

        :param dict log: Dictionary containing logged message with metadata.

        :returns: str
        """
        try:
            chat_data = re.search(r"(?P<room>\[\S+]) (?P<user>\[\S+]) (?P<ip>\[\S+])", log.get("message"))
            if chat_data and log.get("message"):
                message = log["message"].split(": ", 1)[1].replace("\n", "\t")
                subset = {
                    "time": log["time"],
                    "message": message,
                    "level": log["level"].name,
                    "room": chat_data["room"].replace("[", "").replace("]", ""),
                    "user": chat_data["user"].replace("[", "").replace("]", ""),
                    "ip": chat_data["ip"].replace("[", "").replace("]", ""),
                }
                return json.dumps(subset)
        except Exception as e:
            subset["error"] = f"Logging error occurred: {str(e)}"
            return serialize_error(subset)

    def serialize_event(log: dict) -> str:
        """
        Construct warning log.

        :param dict log: Dictionary containing logged message with metadata.

        :returns: str
        """
        try:
            chat_data = re.search(r"(?P<room>\[\S+]) (?P<user>\[\S+])", log["message"])
            if bool(chat_data) and log.get("message") is not None:
                subset = {
                    "time": log["time"],
                    "message": log["message"].split(": ", 1)[1],
                    "level": log["level"].name,
                    "room": chat_data["room"].replace("[", "").replace("]", ""),
                    "user": chat_data["user"].replace("[", "").replace("]", ""),
                }
                return json.dumps(subset)
        except Exception as e:
            log["error"] = f"Logging error occurred: {str(e)}"

    def serialize_error(log: dict) -> str:
        """
        Construct error log record.

        :param dict log: Dictionary containing logged message with metadata.

        :returns: str
        """
        if log and log.get("message"):
            subset = {
                "time": log["time"],
                "level": log["level"].name,
                "message": log["message"],
            }
            return json.dumps(subset)
        elif not log.get("message"):
            subset = {
                "time": log["time"],
                "level": log["level"].name,
                "message": "(No message provided)",
            }
            return json.dumps(subset)

    if record["level"].name == "INFO":
        record["extra"]["serialized"] = serialize_as_admin(record)
        return "{extra[serialized]},\n"
    if record["level"].name in ("TRACE", "WARNING", "SUCCESS"):
        record["extra"]["serialized"] = serialize_event(record)
        return "{extra[serialized]},\n"
    if record["level"].name in ("ERROR", "CRITICAL"):
        record["extra"]["serialized"] = serialize_error(record)
        sms_error_handler(record)
        return "{extra[serialized]},\n"


def construct_json_from_corrupted_log(log: str) -> str:
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
    sms.messages.create(
        body=f'BROBOT ERROR: {log["time"]} | {log["message"]}',
        from_=TWILIO_SENDER_PHONE,
        to=TWILIO_BRO_PHONE_NUMBER,
    )


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
            rotation="300 MB",
            compression="zip",
        )
        # Human-readable error logs
        logger.add(
            "/var/log/broiestbot/error.log",
            colorize=True,
            catch=True,
            level="ERROR",
            format=log_formatter,
            rotation="300 MB",
            compression="zip",
        )
        # Datadog JSON logs
        logger.add(
            "/var/log/broiestbot/info.json",
            format=json_formatter,
            rotation="300 MB",
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
            rotation="300 MB",
            compression="zip",
        )
        # Human-readable error logs
        logger.add(
            f"{BASE_DIR}/logs/errors.log",
            colorize=True,
            catch=True,
            level="ERROR",
            format=log_formatter,
            rotation="300 MB",
            compression="zip",
        )
        # Datadog JSON logs
        logger.add(
            f"{BASE_DIR}/logs/info.json",
            format=json_formatter,
            rotation="300 MB",
            compression="zip",
            level="TRACE",
        )
    return logger


LOGGER = create_logger()
