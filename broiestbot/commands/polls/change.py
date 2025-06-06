"""Conduct a chat poll whether to 'change or stay'."""

from typing import Tuple, Optional, List, Union
from datetime import timedelta

from emoji import emojize
from redis.exceptions import RedisError
from chatango.ch import Room

from clients import r, redis_scheduler
from logger import LOGGER

from config import CHATANGO_SPECIAL_USERS


def change_or_stay_vote(user_name: str, vote: str, room: Room) -> str:
    """
    Conduct chat-wide vote whether to 'change or stay'.
    Each user may cast a single vote, with the results revealed after a fixed time period.

    :param str user_name: Name of user submitting a vote.
    :param str vote: User's submitted vote (either 'change' or 'stay').
    :param Room room: Chatango chat room.

    :returns: str
    """
    try:
        time_remaining = r.ttl("changeorstay")
        change_votes, stay_votes = live_poll_results()
        if (change_votes and user_name in change_votes) or (stay_votes and user_name in stay_votes):
            return emojize(
                f":warning: <b>pls @{user_name} u already voted</b> :warning:\n \
                :hourglass_not_done: Voting ends in <i>{time_remaining} seconds</i>.",
                language="en",
            )
        submit_user_vote(user_name, vote)
        # redis_scheduler.enqueue_in(timedelta(minutes=1), completed_poll_results, room)
        return poll_announcement(user_name, vote)
    except RedisError as e:
        LOGGER.exception(f"RedisError while saving 'change or stay' vote from @{user_name}: {e}")
        return emojize(
            f":warning: my b @{user_name}, broughbert is strugglin with polls atm :warning:",
            language="en",
        )
    except Exception as e:
        LOGGER.exception(f"Unexpected error while saving 'change or stay' vote from @{user_name}: {e}")
        return emojize(
            f":warning: my b @{user_name}, broughbert just broke like a littol BITCH :warning:",
            language="en",
        )


def get_live_poll_results(user_name: str) -> str:
    """
    Summarize the status of an existing poll (if exists).

    :param str user_name: Name of user requesting poll results.

    :returns: str
    """
    time_remaining = r.ttl("changeorstay")
    response = f"\n\n:television: <b>CHANGE OR STAY</b>\n \
                :hourglass_not_done: Voting ends in <i>{time_remaining} seconds</i>.\n\n"
    change_votes, stay_votes = live_poll_results()
    if change_votes or stay_votes:
        response += f":shuffle_tracks_button: !CHANGE: <b>{len(change_votes) if not None else 0} votes</b> ({', '.join(change_votes) if not None else 0})\n \
                      :stop_button: !STAY <b>{len(stay_votes)} votes</b> ({', '.join(stay_votes)})\n"
        return emojize(response, language="en")
    return emojize(f":warning: sry @{user_name}, no change-or-stay poll currently live :warning:", language="en")


def live_poll_results() -> Tuple[Optional[List[str]], Optional[List[str]]]:
    """
    Get live poll results.

    :returns: Tuple[Optional[List[str]], Optional[List[str]]]
    """
    poll_results = r.hgetall("changeorstay")
    change_votes = poll_results.get("change", [])
    stay_votes = poll_results.get("stay", [])
    if change_votes:
        change_votes = change_votes.split(",")
    else:
        change_votes = []
    if stay_votes:
        stay_votes = stay_votes.split(",")
    else:
        stay_votes = []
    return change_votes, stay_votes


def submit_user_vote(user_name: str, vote: str):
    """
    Add user's vote to the poll.

    :param str user_name: Name of user submitting a vote.
    :param str vote: User's submitted vote (either 'change' or 'stay').
    """
    try:
        poll_results = r.hgetall("changeorstay")
        if bool(poll_results) is False:
            r.hset("changeorstay", vote, user_name)
            r.expire("changeorstay", 60)
            if vote == "change":
                r.hset("changeorstay", "stay", "")
            if vote == "stay":
                r.hset("changeorstay", "change", "")
        else:
            current_votes = r.hget("changeorstay", vote)
            if current_votes:
                r.hset("changeorstay", vote, f"{current_votes}," + user_name)
            else:
                r.hset("changeorstay", vote, user_name)
    except Exception as e:
        LOGGER.error(f"Unexpected error while saving 'change or stay' vote from @{user_name}: {e}")


def poll_announcement(user_name: str, vote: str) -> str:
    """
    Summarize the status of a preexisting poll.

    :param str user_name: Name of user submitting a vote.
    :param str vote: User's submitted vote (either 'change' or 'stay').

    :returns: str
    """
    change_votes, stay_votes = live_poll_results()
    time_remaining = r.ttl("changeorstay")
    response = f"\n\n \
        :television: <b>CHANGE OR STAY</b>\n \
        @{user_name} just started a poll and voted to <i>{vote}</i>.\n \
        :hourglass_not_done: Voting ends in <b>{time_remaining} seconds</b>\n \
        --------------\n"
    if change_votes:
        response += f":shuffle_tracks_button: !CHANGE: <b>{len(change_votes)} votes</b> ({', '.join(change_votes) if change_votes else ''})\n"
    if stay_votes:
        response += (
            f":stop_button: !STAY <b>{len(stay_votes)} votes</b> ({', '.join(stay_votes) if stay_votes else ''})"
        )
    else:
        response += ":stop_button: !STAY <b>0 votes</b>"
    return emojize(response, language="en")


def completed_poll_results(room: Room):
    """
    Post `change or stay` poll results.

    :param Room room: Chatango chat room.

    :returns: str
    """
    response = f"\n\n<b>:television: <b>CHANGE OR STAY RESULTS!!!</b>\n"
    change_votes, stay_votes = live_poll_results()
    num_change_votes = len(change_votes) if change_votes else 0
    num_stay_votes = len(stay_votes) if stay_votes else 0
    if num_change_votes > num_stay_votes:
        response += f"Chat has voted to <b>CHANGE!</b> {'@ '.join(CHATANGO_SPECIAL_USERS)}\n"
    elif num_change_votes < num_stay_votes:
        response += f"Chat has voted to <b>STAY!</b> Don't touch that dial!\n"
    elif num_change_votes == num_stay_votes:
        response += f"Poll ended in a <i>STALEMATE!</i>\n \
                    AAAAAA IDK HOW TO HANDOL THIS!!\n"
    response += f":shuffle_tracks_button: !CHANGE: <b>{num_change_votes} votes</b>: ({', '.join(change_votes)})\n \
                  :stop_button: !STAY <b>{num_stay_votes} votes</b>: ({', '.join(stay_votes)})"
    room.message(emojize(response, language="en"))
