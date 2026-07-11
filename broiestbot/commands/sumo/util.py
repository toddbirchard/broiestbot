"""Tools for formatting sumo match data."""


def format_rank(rank: str) -> str:
    """
    Make each Rikishi rank more readable (`Maegashira 15 East` -> `前頭 15`).

    :param str rank: Full rank string from the API.

    :returns: str
    """
    rank_abbr_map = {
        "Maegashira": "前頭",
        "Juryo": "十両",
        "Sekiwake": "関脇",
        "Komusubi": "小結",
        "Ozeki": "大関",
        "Yokozuna": "横綱",
    }
    rank_name, _, rank_seed = rank.partition(" ")
    rank_name = rank_abbr_map.get(rank_name, rank_name)
    rank_seed.replace("East", "東").replace("West", "西")
    return f"{rank_name} {rank_seed}".strip()
