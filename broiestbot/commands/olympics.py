"""2028 Olympics & 2026 Winter Olympics medal leaders"""

import pandas as pd
from emoji import emojize
from logger import LOGGER
from pandas import Series

from config import OLYMPICS_LEADERBOARD_ENDPOINT, WINTER_OLYMPICS_LEADERBOARD_ENDPOINT


def get_summer_olympic_medals() -> str:
    """
    Summer Olympics country leaders, by number of gold medals.

    :returns: str
    """
    return get_medals_by_nation(OLYMPICS_LEADERBOARD_ENDPOINT)


def get_winter_olympic_medals() -> str:
    """
    Winter Olympics country leaders, by number of gold medals.

    :returns: str
    """
    return get_medals_by_nation(WINTER_OLYMPICS_LEADERBOARD_ENDPOINT)


def get_medals_by_nation(endpoint: str) -> str:
    """
    Fetch olympic medal leaders and format leaderboard.

    :param str endpoint: URL containing olympic medal leaders to scrape.

    :returns: str
    """
    try:
        medals_df = pd.read_html(
            endpoint,
            flavor="bs4",
            attrs={"class": "medals olympics has-team-logos"},
            header=0,
            index_col=None,
        )
        medals_df = medals_df[0].head(15)
        medals_df.sort_values(by=["G", "Total"], ascending=False, inplace=True)
        medals_df.rename(
            columns={
                "Group": "Nation&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;",
                "G": "🥇&nbsp;&nbsp;&nbsp;",
                "S": "🥈&nbsp;&nbsp;&nbsp;",
                "B": "🥉&nbsp;&nbsp;&nbsp;",
                "Total": "#️⃣",
            },
            inplace=True,
        )
        medals_df["Nation&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"] = medals_df[
            "Nation&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        ].apply(add_nation_flag_emojis)
        medals_df["Nation&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"] = medals_df[
            "Nation&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        ].apply(lambda x: f"{x}&nbsp;&nbsp;")
        medals_df["🥇&nbsp;&nbsp;&nbsp;"] = medals_df["🥇&nbsp;&nbsp;&nbsp;"].apply(
            lambda x: f"{x}&nbsp;&nbsp;&nbsp;&nbsp;"
        )
        medals_df["🥈&nbsp;&nbsp;&nbsp;"] = medals_df["🥈&nbsp;&nbsp;&nbsp;"].apply(
            lambda x: f"{x}&nbsp;&nbsp;&nbsp;&nbsp;"
        )
        medals_df["🥉&nbsp;&nbsp;&nbsp;"] = medals_df["🥉&nbsp;&nbsp;&nbsp;"].apply(
            lambda x: f"{x}&nbsp;&nbsp;&nbsp;&nbsp;"
        )
        return f"\n\n\n\n\n\n\n\n<div>\n</div>{medals_df.to_string(header=True, index=False)}"
    except Exception as e:
        LOGGER.exception(f"Exception occurred while fetching winter olympics leaderboard: {e}")
        return emojize(":warning: lmao nobody has won anything yet retart :warning:", language="en")


def add_nation_flag_emojis(row: Series):
    """
    Add flag emojis to Olympic leaders.

    :param Series row: Row containing number of medals per nation.

    :returns: Series
    """
    row = (
        row.replace("NORNorway", "🇳🇴 NOR")
        .replace("USAUnited States", "🇺🇸 USA")
        .replace("NEDNetherlands", "🇳🇱 NED")
        .replace("GERGermany", "🇩🇪 GER")
        .replace("SWESweden", "🇸🇪 SWE")
        .replace("AUTAustria", "🇦🇹 AUT")
        .replace("CHNChina", "🇨🇳 CHN")
        .replace("ROCRussian Olympic Committee", "🇷🇺 ROC")
        .replace("ITAItaly", "🇮🇹 ITA&nbsp;&nbsp;")
        .replace("SUISwitzerland", "🇨🇭 SUI&nbsp;")
        .replace("CANCanada", "🇨🇦 CAN")
        .replace("FRAFrance", "🇫🇷 FRA")
        .replace("KORSouth Korea", "🇰🇷 KOR")
        .replace("AUSAustralia", "🇦🇺 AUS")
        .replace("FINFinland", "🇫🇮 FIN&nbsp;&nbsp;")
        .replace("SLOSlovenia", "🇸🇮 SLO")
        .replace("HUNHungary", "🇭🇺 HUN")
        .replace("POL", "🇵🇱 POL")
        .replace("NZLNew Zealand", "🇳🇿 NZL")
        .replace("JPNJapan", "🇯🇵 JPN")
        .replace("GBRGreat Britain", "🇬🇧 GBR")
        .replace("CZECzechia", "🇨🇿 CZE")
        .replace("ESPSpain", "🇪🇸 ESP")
        .replace("DENDenmark", "🇩🇰 DEN")
        .replace("BELBelgium", "🇧🇪 BEL")
        .replace("UKRUkraine", "🇺🇦 UKR")
        .replace("INDIndia", "🇮🇳 IND")
        .replace("GREGreece", "🇬🇷 GRE")
        .replace("IRNIran", "🇮🇷 IRN")
        .replace("PORPortugal", "🇵🇹 POR")
        .replace("SRBSrbia", "🇷🇸 SRB")
        .replace("CROCroatia", "🇭🇷 CRO")
        .replace("MEXMexico", "🇲🇽 MEX")
        .replace("BULBulgaria", "🇧🇬 BUL")
    )
    return f"<b>{row}</b>&nbsp;&nbsp;"


def format_country_name(value: str):
    return f"{value}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
