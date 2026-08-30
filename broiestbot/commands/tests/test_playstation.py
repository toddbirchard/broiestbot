"""Tests for the PSN online-friends command.

`get_presence()` is a network call per friend. It used to be made twice for every friend
who was in a game — once to filter the roster, once to render the line — so the presence
payload is now carried alongside the friend instead of re-fetched.
"""

from unittest.mock import MagicMock, patch

from broiestbot.commands.playstation import (
    create_psn_response,
    get_active_friends,
    get_psn_online_friends,
)


def build_friend(name: str, in_game: bool = True, presence_counter: dict = None) -> MagicMock:
    """
    Build a stand-in PSN friend whose `get_presence()` calls are counted.

    :param str name: The friend's online ID.
    :param bool in_game: Whether the friend is currently playing something.
    :param dict presence_counter: Mutable counter incremented on each `get_presence()` call.

    :returns: MagicMock
    """
    friend = MagicMock()
    friend.online_id = name

    def get_presence():
        if presence_counter is not None:
            presence_counter["calls"] = presence_counter.get("calls", 0) + 1
        return {
            "basicPresence": {
                "gameTitleInfoList": [{"titleName": f"Game-{name}"}] if in_game else None,
                "primaryPlatformInfo": {"platform": "PS5"},
            }
        }

    friend.get_presence = get_presence
    return friend


def test_presence_is_fetched_once_per_friend():
    """Each friend costs exactly one presence call, not one per pass over the roster."""
    counter = {}
    friends = [build_friend(f"friend{i}", in_game=True, presence_counter=counter) for i in range(5)]

    with patch("broiestbot.commands.playstation.psn") as psn:
        psn.account.online_id = "broiestbro"
        psn.get_online_friends.return_value = friends
        response = get_psn_online_friends()

    assert counter["calls"] == len(friends), f"expected {len(friends)} presence calls, got {counter['calls']}"
    assert response.count("playing") == len(friends)


def test_only_in_game_friends_are_listed():
    """Friends who are online but not in a game are filtered out."""
    counter = {}
    friends = [build_friend(f"friend{i}", in_game=(i % 2 == 0), presence_counter=counter) for i in range(6)]

    with patch("broiestbot.commands.playstation.psn") as psn:
        psn.account.online_id = "broiestbro"
        psn.get_online_friends.return_value = friends
        response = get_psn_online_friends()

    assert counter["calls"] == 6, "every online friend is checked exactly once"
    assert response.count("playing") == 3
    for name in ("friend0", "friend2", "friend4"):
        assert name in response
    for name in ("friend1", "friend3", "friend5"):
        assert name not in response


def test_unreachable_friend_does_not_sink_the_roster():
    """A friend whose presence lookup raises is skipped; the rest still render."""
    good = build_friend("good_friend")
    broken = MagicMock()
    broken.online_id = "broken_friend"
    broken.get_presence.side_effect = RuntimeError("PSN timed out")

    active = get_active_friends([broken, good])

    assert [friend.online_id for friend, _ in active] == ["good_friend"]
    assert "good_friend" in create_psn_response(active)


def test_no_active_friends_reports_no_friends():
    """A roster where nobody is in a game falls through to the 'no friends' response."""
    friends = [build_friend(f"friend{i}", in_game=False) for i in range(3)]

    with patch("broiestbot.commands.playstation.psn") as psn:
        psn.account.online_id = "broiestbro"
        psn.get_online_friends.return_value = friends
        response = get_psn_online_friends()

    assert "has no friends" in response


def test_failure_before_account_lookup_still_responds():
    """An exception on the very first call must not raise `NameError` from the handler."""
    with patch("broiestbot.commands.playstation.psn") as psn:
        type(psn).account = property(lambda _: (_ for _ in ()).throw(RuntimeError("PSN down")))
        response = get_psn_online_friends()

    assert "has no friends" in response
