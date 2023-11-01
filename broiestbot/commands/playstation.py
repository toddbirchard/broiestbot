"""PSN Commands"""
from typing import List, Optional
from math import floor
from psnawp_api.models.user import User
from psnawp_api.models.trophies.trophy_titles import TrophyTitles
from psnawp_api.utils import request_builder
from emoji import emojize

from clients import psn

from config import PLAYSTATION_EAFC_2024_ID

from logger import LOGGER


def get_psn_online_friends() -> str:
    """
    Get list of all online friends of a PSN user.

    :returns: str
    """
    try:
        psn_account = psn.account.online_id
        online_friends = psn.get_online_friends()
        if bool(online_friends):
            active_friends = get_active_friends(online_friends)
            if active_friends or online_friends:
                return create_psn_response(active_friends, online_friends)
        return emojize(f"\n\n:video_game: <b>{psn_account}</b> has no friends.", language="en")
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching PSN friends: {e}")
        return emojize(f"\n\n:video_game: <b>{psn_account}</b> has no friends.", language="en")


def get_active_friends(online_friends: List[User]) -> List[Optional[User]]:
    """
    Get PSN user profile for a given online ID.

    :param friends List[User]: List of PSN friends.
    :returns: List[Optional[User]]
    """
    return [
        friend
        for friend in online_friends
        if friend.get_presence()["basicPresence"].get("gameTitleInfoList") is not None
    ]


def create_psn_response(active_friends: List[User], online_friends: List[User]) -> str:
    """
    Construct chat response of active PSN friends.

    :param str user: PSN User ID.
    :param List[User] friends: List of PSN friends.

    :returns: str
    """
    response = emojize("\n\n:video_game: <b>BROIESTBRO's online PSN friends</b>:\n", language="en")
    for active_friend in active_friends:
        response += create_active_psn_user_response(active_friend)
    return response


def create_active_psn_user_response(active_friend: User) -> str:
    """
    Create response for active PSN user.

    :param str account_name: PSN User ID.
    :param str friend_meta: PSN User online presence data.

    :returns: str
    """
    try:
        friend_meta = active_friend.get_presence()
        playing_game = friend_meta["basicPresence"]["gameTitleInfoList"][0]["titleName"]
        platform = friend_meta["basicPresence"]["primaryPlatformInfo"]["platform"]
        return f"• <b>{active_friend.online_id}</b>: playing {playing_game} on {platform}\n"
    except Exception as e:
        LOGGER.exception(e)


def get_psn_game_trophies():
    """List all game trophies earned by user."""
    try:
        trophies = psn.account.trophies(
            np_communication_id=PLAYSTATION_EAFC_2024_ID, platform=["PS5", "PS4"], limit=100, include_metadata=True
        )
        for trophy in trophies:
            LOGGER.info(trophy)
        # trophies = [trophy["trophyName"] for trophy in trophies if trophy["earned"]]
        return trophies
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching PSN trophies: {e}")


def get_trophy_titles():
    get_trophy_titles


def get_titles_with_stats():
    """Get games and associated playing time"""
    raw_games_with_stats = psn.account.title_stats(limit=4)
    games_with_stats = parse_title_stats(raw_games_with_stats)
    print(f"titles_with_stats = {games_with_stats}")
    return games_with_stats


def parse_title_stats(titles) -> str:
    """Parse title stats into chat response"""
    title_response = "\n\n\n"
    i = 0
    for title in titles:
        i += 1
        hours_played = floor(round(title.play_duration.total_seconds(), 0) / 60 / 60)
        title_response += f"\n<b>{title.name}</b>\n"
        title_response += f":chart_increasing: Times played: {title.play_count}\n"
        title_response += f":calendar: First played: {title.first_played_date_time.date().strftime('%b %e, %Y')}\n"
        title_response += (
            f":tear-off_calendar: Last Played: {title.last_played_date_time.date().strftime('%b %e, %Y')}\n"
        )
        title_response += f":hourglass_not_done: Time played:  {'{:,}'.format(hours_played)} hours \n"
        title_response += f"{title.image_url}"
        if i < 4:
            title_response += "\n\n-------------------\n"
    return emojize(title_response, language="en")
