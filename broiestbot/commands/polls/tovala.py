"""Allow users to track consecutive Tovala streaks via Redis cache."""

from database import session
from database.models import PollResult
from emoji import emojize
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from clients import r
from logger import LOGGER


def tovala_counter(user_name: str) -> str:
    """
    Keep track of consecutive Tovalas.

    :param str user_name: Name of user reporting a Tovala sighting.

    :returns: str
    """
    try:
        r.hincrby("tovala", user_name, 1)
        r.expire("tovala", 60)
        tovala_users = r.hgetall("tovala")
        tovala_contributors = tally_tovala_sightings_by_user(tovala_users)
        session_total_sightings = total_tovala_sightings(tovala_users)
        standing_total_sightings = get_current_total()
        LOGGER.success(f"Saved Tovala sighting to Redis: (tovala, {user_name})")
        return emojize(
            f"\n\n<b>:shallow_pan_of_food: {session_total_sightings} CONSECUTIVE TOVALAS!</b>\n{tovala_contributors}\n:keycap_#: Highest streak: {standing_total_sightings}",
            language="en",
        )
    except RedisError as e:
        LOGGER.exception(f"RedisError while saving Tovala streak from @{user_name}: {e}")
        return emojize(
            f":warning: my b @{user_name}, broughbert just broke like a littol BITCH :warning:",
            language="en",
        )
    except Exception as e:
        LOGGER.exception(f"Unexpected error while saving Tovala streak from @{user_name}: {e}")
        return emojize(
            f":warning: my b @{user_name}, broughbert just broke like a littol BITCH :warning:",
            language="en",
        )


def tally_tovala_sightings_by_user(tovala_users: dict) -> str:
    """
    Construct summary of reported Tovala sightings by user.

    :param dict tovala_users: Map of Tovala sightings by username.

    :returns: str
    """
    contributors = ":bust_in_silhouette: Contributors: "
    for k, v in tovala_users.items():
        contributors += f"{k}: {v}, "
    return contributors.rstrip(", ")


def total_tovala_sightings(tovala_users: dict) -> int:
    """
    Aggregate sum of all Tovala sightings.

    :param dict tovala_users: Map of Tovala sightings by username.

    :returns: int
    """
    total_count = 0
    for user_count in tovala_users.values():
        total_count += int(user_count)
    return total_count


def get_current_total() -> int:
    """
    Get current running Tovala streak from database.

    :returns: int
    """
    try:
        total_count = session.query(PollResult).filter(PollResult.type == "tovala").one_or_none()
        if total_count is not None:
            return total_count.count
        return 0
    except SQLAlchemyError as e:
        LOGGER.exception(f"SQLAlchemyError while fetching Tovala total count: {e}")
        return 0
    except Exception as e:
        LOGGER.exception(f"Unexpected exception while fetching Tovala total count: {e}")
        return 0
