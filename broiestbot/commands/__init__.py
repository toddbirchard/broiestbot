"""Construct responses to bot commands from third-party APIs."""
from .afterdark import get_redgifs_gif
from .definitions import (
    get_english_definition,
    get_english_translation,
    get_urban_definition,
    wiki_summary,
)
from .embeds import create_instagram_preview, generate_twitter_preview
from .footy import (
    all_leagues_golden_boot,
    epl_golden_boot,
    fetch_fox_fixtures,
    footy_all_upcoming_fixtures,
    footy_live_fixture_stats,
    footy_live_fixtures,
    footy_team_lineups,
    footy_today_fixtures_odds,
    footy_upcoming_fixtures,
    get_today_footy_odds_for_league,
    league_table_standings,
    mls_standings,
    today_upcoming_fixtures,
)
from .images import (
    fetch_latest_image_from_gcs_bucket,
    fetch_random_image_from_gcs_bucket,
    gcs_count_images_in_bucket,
    giphy_image_search,
    random_image,
    spam_random_images_from_gcs_bucket,
    subreddit_image,
)
from .lyrics import get_song_lyrics
from .markets import get_crypto_chart, get_crypto_price, get_stock, get_top_crypto
from .misc import (
    blaze_time_remaining,
    covid_cases_usa,
    send_text_message,
    time_until_wayne,
)
from .mlb import today_phillies_games
from .movies import find_imdb_movie
from .nba import live_nba_games, nba_standings, upcoming_nba_games
from .nfl import get_live_nfl_games
from .odds import get_odds
from .olympics import get_summer_olympic_medals, get_winter_olympic_medals
from .playstation import get_psn_online_friends
from .polls import (
    bach_gang_counter,
    change_or_stay_vote,
    completed_poll_results,
    get_live_poll_results,
    tovala_counter,
)
from .previews import extract_url
from .tuner import get_current_show, tuner

# from .video import search_youtube_for_video
from .video import get_all_live_twitch_streams
from .weather import get_current_weather


def basic_message(message):
    """Send basic text message to room."""
    return message
