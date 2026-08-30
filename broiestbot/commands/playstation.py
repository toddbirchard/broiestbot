"""PSN Commands"""

from math import floor
from typing import List, Optional, Tuple

from emoji import emojize
from logger import LOGGER
from psnawp_api.models.user import User

from clients import psn
from config import PLAYSTATION_EAFC_2025_ID


def get_psn_online_friends() -> str:
    """
    Get list of all online friends of a PSN user.

    :returns: str
    """
    psn_account = "BROIESTBRO"
    try:
        psn_account = psn.account.online_id
        online_friends = psn.get_online_friends()
        if bool(online_friends):
            active_friends = get_active_friends(online_friends)
            if active_friends:
                return create_psn_response(active_friends)
        return emojize(f"\n\n:video_game: <b>{psn_account}</b> has no friends.", language="en")
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching PSN friends: {e}")
        return emojize(f"\n\n:video_game: <b>{psn_account}</b> has no friends.", language="en")


def get_active_friends(online_friends: List[User]) -> List[Tuple[User, dict]]:
    """
    Pair each friend who is currently in a game with their presence payload.

    The presence payload is carried alongside the friend rather than re-fetched when the
    response is built: `get_presence()` is a network call, and fetching it once per friend
    instead of twice halves the round trips this command makes.

    :param List[User] online_friends: PSN friends who are currently online.

    :returns: List[Tuple[User, dict]]
    """
    active_friends = []
    for friend in online_friends:
        try:
            presence = friend.get_presence()
        except Exception as e:
            # One unreachable friend shouldn't cost the whole roster.
            LOGGER.warning(f"Could not fetch PSN presence for `{getattr(friend, 'online_id', friend)}`: {e}")
            continue
        if presence["basicPresence"].get("gameTitleInfoList") is not None:
            active_friends.append((friend, presence))
    return active_friends


def create_psn_response(active_friends: List[Tuple[User, dict]]) -> str:
    """
    Construct chat response of active PSN friends.

    :param List[Tuple[User, dict]] active_friends: Online PSN friends & their presence data.

    :returns: str
    """
    response = emojize("\n\n:video_game: <b>BROIESTBRO's online PSN friends</b>:\n", language="en")
    for active_friend, presence in active_friends:
        friend = create_active_psn_user_response(active_friend, presence)
        if friend:
            response += friend
    return response


def create_active_psn_user_response(active_friend: User, friend_meta: dict) -> Optional[str]:
    """
    Create response for active PSN user.

    :param User active_friend: PSN friend who is currently online.
    :param dict friend_meta: PSN user online presence data, already fetched by `get_active_friends`.

    :returns: Optional[str]
    """
    try:
        playing_game = friend_meta["basicPresence"]["gameTitleInfoList"][0]["titleName"]
        platform = friend_meta["basicPresence"]["primaryPlatformInfo"]["platform"]
        return f"• <b>{active_friend.online_id}</b>: playing {playing_game} on {platform}\n"
    except Exception as e:
        LOGGER.exception(e)


def get_psn_game_trophies():
    """List all game trophies earned by user."""
    try:
        trophies = psn.account.trophies(
            np_communication_id=PLAYSTATION_EAFC_2025_ID, platform=["PS5", "PS4"], limit=100
        )
        for trophy in trophies:
            LOGGER.info(trophy)
        # trophies = [trophy["trophyName"] for trophy in trophies if trophy["earned"]]
        return trophies
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching PSN trophies: {e}")


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
