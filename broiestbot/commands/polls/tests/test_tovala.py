"""Allow users to track consecutive Tovala streaks via Redis cache."""

from typing import Dict
from unittest.mock import patch

from emoji import emojize

from broiestbot.commands.polls import tally_tovala_sightings_by_user, tovala_counter
from config import CHATANGO_BOTS


def test_tovala_counter(redis_mock, tovala_poll_results: Dict[str, str]):
    """
    Conduct a mock Tovala streak & ensure value are stored correctly.

    :param FakeRedis redis_mock: In-memory Redis instance.
    :param Dict[str, str] tovala_poll_results: Example result of a collective Tovala sighting between all bots.
    """
    with (
        patch("broiestbot.commands.polls.tovala.r", redis_mock),
        patch("broiestbot.commands.polls.tovala.get_current_total", return_value=3),
    ):
        flush_tovala_cache(redis_mock)
        for username in CHATANGO_BOTS:
            counter = tovala_counter(username.lower())
            assert redis_mock.hexists("tovala", username.lower()) is True
            assert redis_mock.hget("tovala", username.lower()) == str(1)
            assert formatted_tovala_result(redis_mock) == counter
        assert redis_mock.hgetall("tovala") == tovala_poll_results


def flush_tovala_cache(r):
    """
    Remove existing Tovala hash prior to running test.

    :param FakeRedis r: In-memory Redis instance.
    """
    for username in CHATANGO_BOTS:
        r.hdel("tovala", username.lower())
    assert len(r.hgetall("tovala")) == 0


def formatted_tovala_result(r) -> str:
    """
    Format existing Tovala poll results into a text-based response.

    :param FakeRedis r: In-memory Redis instance.

    :returns: str
    """
    number_tovalas = len(r.hvals("tovala"))
    tovala_users = r.hgetall("tovala")
    return emojize(
        f"\n\n<b>:shallow_pan_of_food: {number_tovalas} CONSECUTIVE TOVALAS!</b>\n{tally_tovala_sightings_by_user(tovala_users)}\n:keycap_#: Highest streak: 3",
        language="en",
    )
