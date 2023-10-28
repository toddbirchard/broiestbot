"""Track number of cliche phrases uttered on The Bachelor."""
from datetime import datetime, timedelta
from config import TIMEZONE_US_EASTERN
from database import session
from database.models import PollResult
from emoji import emojize
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from clients import r
from logger import LOGGER


def bach_gang_counter(user_name: str, phrase: str) -> str:
    """
    Persist number of cliché words record by users during The Bachelor.

    :param str user_name: Username of user reporting a cliché word.
    :param str phrase: Overly-used phrase (e.g. "vulnerable", "journey", "connection")

    :returns: str
    """
    try:
        is_live = is_bachelor_currently_live()
        if not is_live:
            return emojize("", language="en")
        create_bach_poll_if_needed()
        update_recorded_counts_for_phrase(user_name, phrase)
        bachelor_word_count_by_user = tally_words_per_user()
        bachelor_total_word_count = aggregate_cliche_words_recorded(phrase)
        LOGGER.success(f"Persisted Bachelor word to Redis: ({phrase}, {user_name})")
        return emojize(
            f"\n\n:man_in_tuxedo_light_skin_tone: :woman_with_veil_light_skin_tone: <b>BACH GANG IS IN SESSION!</b>\n \
            :bust_in_silhouette: {bachelor_word_count_by_user}\n \
            :input_numbers: {bachelor_total_word_count}",
            language="en",
        )
    except RedisError as e:
        LOGGER.error(f"RedisError while persisting bach word {phrase} from @{user_name}: {e}")
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


def create_bach_poll_if_needed():
    """
    Initialize Redis counter if does not currently exist.
    Assign Redis record a TTL of 2 hours (duration of show).

    :returns: None
    """
    if not r.hgetall("bachcount"):
        r.expire("bachcount", 7200)


def update_recorded_counts_for_phrase(user_name: str, phrase: str):
    """
    Update newly recorded values for a given phrase by adding to preexisting value.

    :param str user_name: Username of user reporting a cliché word.
    :param str phrase: Overly-used phrase (e.g. "vulnerable", "journey", "connection")
    """
    try:
        bach_phrases = r.hget("bachcount", phrase)
        if bach_phrases is None:
            r.hset("bachcount", phrase, user_name)
            create_bach_poll_if_needed()
        else:
            LOGGER.info(f"bach_phrases = {bach_phrases}")
            bach_phrases += f"{user_name}"
            bach_phrases = r.hset("bachcount", phrase, bach_phrases)
            LOGGER.info(f"bach_phrases = {bach_phrases}")
    except RedisError as e:
        LOGGER.error(f"RedisError while persisting bach word {phrase} from @{user_name}: {e}")
        return emojize(
            f":warning: my b @{user_name}, broughbert just broke like a littol BITCH :warning:",
            language="en",
        )
    except Exception as e:
        LOGGER.exception(f"Unexpected error while persisting bach word {phrase} from @{user_name}: {e}")
        return emojize(
            f":warning: my b @{user_name}, broughbert just broke like a littol BITCH :warning:",
            language="en",
        )


def tally_words_per_user() -> str:
    """
    Construct summary of reported Tovala sightings by user.

    :param dict tovala_users: Map of Tovala sightings by username.

    :returns: str
    """
    current_results = r.hgetall("bachcount")
    LOGGER.warning(f"current_results = {current_results}")
    response_summary = ":bust_in_silhouette: Contributors:\n"
    for k, v in current_results.items():
        response_summary += f"{k}: {v}, "
    return response_summary.rstrip(", ")


def aggregate_cliche_words_recorded(tovala_users: dict) -> int:
    """
    Aggregate sum of all Tovala sightings.

    :param dict tovala_users: Map of Tovala sightings by username.

    :returns: int
    """
    total_count = 0
    for user_count in tovala_users.values():
        total_count += int(user_count)
    return total_count


def is_bachelor_currently_live() -> bool:
    """
    Determine whether `The Bachelor` is currently live.

    :returns: bool
    """
    try:
        now = datetime.now(tz=TIMEZONE_US_EASTERN)
        weekday = datetime.today().weekday()
        bachelor_start_time = now.replace(hour=20, minute=0, second=0)
        bachelor_end_time = bachelor_start_time + timedelta(hours=2)
        if weekday == 0 and (bachelor_start_time <= now <= bachelor_end_time):
            return True
        return False
    except Exception as e:
        LOGGER.exception(f"Unexpected error while determining whether The Bachelor is on: {e}")
        return False
