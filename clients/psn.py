"""PSN account API client."""

from typing import Optional, List
from psnawp_api import PSNAWP
from psnawp_api.models.user import User
from psnawp_api.models.client import Client

# from psnawp_api.models.trophies.trophy import Trophy

from config import PLAYSTATION_EAFC_2025_ID


class PlaystationClient:
    """Playstation client for a logged-in PSN user."""

    def __init__(self, token: str):
        self.psn = PSNAWP(token)
        self.eafc = PLAYSTATION_EAFC_2025_ID

    @property
    def account(self) -> Client:
        """
        Get logged-in PSN account.

        :returns: Client
        """
        return self.psn.me()

    def get_online_friends(self) -> List[Optional[User]]:
        """
        Get friends of logged-in PSN user.

        :returns: List[Optional[User]]
        """
        friends = self.account.friends_list()
        online_friends = [
            friend for friend in friends if friend.get_presence()["basicPresence"]["availability"] == "availableToPlay"
        ]
        return online_friends

    def get_user(self, online_id: str) -> Optional[User]:
        """
        Get PSN user profile for a given online ID.

        :param online_id str: PSN User ID.

        :returns: Optional[User]
        """
        return self.psn.user(online_id=online_id)

    '''def get_earned_trophies_for_game(self, game_id) -> Iterator[Trophy]:
        """
        Fetch game details by PS5 ID.

        :param str game_id: PS5 game ID.

        :returns: Iterator[Trophy]
        """
        trophies_per_game = self.account.trophies(np_communication_id=game_id, platform=["PS5"])
        trophy_breakdown = [trophy for trophy in trophies_per_game.from_trophy_dict["trophies"] if trophy["earned"]]
        print(f"trophy_breakdown = {trophy_breakdown}")
        return trophy_breakdown'''
