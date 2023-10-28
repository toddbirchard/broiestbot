"""Persist user metadata."""
from typing import Optional
from datetime import datetime
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from database import session
from database.models import ChatangoUser

from chatango.ch import Message, User
from clients import geo
from config import PERSIST_USER_DATA
from logger import LOGGER


def persist_user_data(room_name: str, user: User, message: Message, bot_username: str) -> None:
    """
    Persist user metadata.

    :param str room_name: Chatango room.
    :param User user: User responsible for triggering command.
    :param Message message: User submitted message.
    :param str bot_username: Name of the currently run bot.

    :returns: None
    """
    try:
        if message.ip and PERSIST_USER_DATA and bot_username in ("broiestbro", "broiestbot"):
            existing_user = fetch_existing_user(room_name, user, message)
            if existing_user is None:
                user_data = geo.lookup_user_by_ip(message.ip)
                if user_data:
                    user_asn_data = user_data.get("asn")
                    user_language_data = user_data.get("languages")[0]
                    user_currency_data = user_data.get("currency")
                    user_threat_data = user_data.get("threat")
                    user_timezone_data = user_data.get("time_zone")
                    user_carrier_data = user_data.get("carrier")
                    # fmt: off
                    session.add(
                        ChatangoUser(
                            username=user.name.lower().replace("!anon", "anon"),
                            chatango_room=room_name,
                            ip=message.ip,
                            city=user_data.get("city"),
                            region=user_data.get("region"),
                            country_name=user_data.get("country_name"),
                            company=user_data.get("company"),
                            latitude=user_data.get("latitude"),
                            longitude=user_data.get("longitude"),
                            postal=user_data.get("postal"),
                            emoji_flag=user_data.get("emoji_flag"),
                            language=user_language_data.get("name") if user_language_data else None,
                            currency_name=user_currency_data.get("name") if user_currency_data else None,
                            currency_symbol=user_currency_data.get("symbol") if user_currency_data else None,
                            time_zone_name=user_timezone_data.get("name") if user_timezone_data else None,
                            time_zone_abbr=user_timezone_data.get("abbr") if user_timezone_data else None,
                            time_zone_offset=user_timezone_data.get("offset") if user_timezone_data else None,
                            time_zone_is_dst=user_timezone_data.get("is_dst") if user_timezone_data else None,
                            time_zone_current_time=user_timezone_data.get("current_time") if user_timezone_data else None,
                            carrier_name=user_carrier_data.get("name") if user_carrier_data else None,
                            carrier_mnc=user_carrier_data.get("mnc") if user_carrier_data else None,
                            carrier_mcc=user_carrier_data.get("mcc") if user_carrier_data else None,
                            asn_asn=user_asn_data.get("asn") if user_asn_data else None,
                            asn_name=user_asn_data.get("name") if user_asn_data else None,
                            asn_domain=user_asn_data.get("domain") if user_asn_data else None,
                            asn_route=user_asn_data.get("route") if user_asn_data else None,
                            asn_type=user_asn_data.get("type") if user_asn_data else None,
                            is_tor=user_threat_data.get("is_tor") if user_threat_data else None,
                            is_proxy=user_threat_data.get("is_proxy") if user_threat_data else None,
                            is_known_attacker=user_threat_data.get("is_known_attacker") if user_threat_data else None,
                            is_threat=user_threat_data.get("is_threat") if user_threat_data else None,
                            created_at=datetime.now()
                        )
                    )
                    # fmt: on
    except IntegrityError as e:
        LOGGER.exception(f"Failed to save duplicate entry for {user.name}: {e}")
    except SQLAlchemyError as e:
        LOGGER.exception(f"SQLAlchemyError while persisting data for user {user.name}: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error while attempting to save data for {user.name}: {e}")


def fetch_existing_user(room_name: str, user: User, message: Message) -> Optional[ChatangoUser]:
    """
    Persist metadata regarding message history.

    :param str room_name: Chatango room.
    :param User user: User responsible for triggering command.
    :param Message message: User submitted message.

    :returns: Optional[ChatangoUser]
    """
    try:
        if message.ip:
            return (
                session.query(ChatangoUser)
                .filter(
                    ChatangoUser.username == user.name.lower(),
                    ChatangoUser.chatango_room == room_name,
                    ChatangoUser.ip == message.ip,
                )
                .first()
            )
    except SQLAlchemyError as e:
        LOGGER.exception(f"SQLAlchemyError occurred while fetching metadata for {user.name}: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error while attempting to save data for {user.name}: {e}")
