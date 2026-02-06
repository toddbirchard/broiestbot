"""Construct responses to bot commands from third-party APIs."""

from .afterdark import get_redgifs_gif
from .definitions import (
    get_english_definition,
    get_english_translation,
    get_urban_definition,
    wiki_summary,
    create_wiki_preview,
)
from .embeds import create_instagram_preview, generate_twitter_preview
from .footy import (
    all_leagues_golden_boot,
    epl_golden_boot,
    fetch_fox_fixtures,
    footy_all_upcoming_fixtures,
    footy_live_fixtures,
    footy_today_fixtures_odds,
    footy_team_lineups,
    footy_upcoming_fixtures,
    get_today_footy_odds_for_league,
    today_upcoming_fixtures,
    league_table_standings,
    mls_standings,
    footy_stats_for_live_fixtures,
    fetch_aafk_fixture_data,
)
from .images import (
    fetch_random_image_from_gcs_bucket,
    gcs_count_images_in_bucket,
    spam_random_images_from_gcs_bucket,
    fetch_latest_image_from_gcs_bucket,
    giphy_image_search,
    random_image,
    subreddit_image,
)
from .lyrics import get_song_lyrics
from .markets import get_crypto_chart, get_crypto_price, get_stock, get_top_crypto
from .misc import (
    blaze_time_remaining,
    nontent_time_remaining,
    covid_cases_usa,
    send_text_message,
    time_until_wayne,
)
from .mlb import today_phillies_games
from .movies import find_imdb_movie, find_movie, streaming_service_show
from .nba import live_nba_games, nba_standings, upcoming_nba_games
from .nfl import get_today_nfl_games, get_live_nfl_game_summaries, fetch_sleeper_matchups
from .olympics import get_summer_olympic_medals, get_winter_olympic_medals
from .polls import change_or_stay_vote, tovala_counter, get_live_poll_results, completed_poll_results, bach_gang_counter
from .previews import extract_url
from .tuner import get_current_show, tuner

# from .video import search_youtube_for_video
from .video import get_all_live_twitch_streams, generate_youtube_video_preview, search_youtube_video
from .weather import get_current_weather
from .playstation import get_psn_online_friends, get_psn_game_trophies, get_titles_with_stats
from .odds import get_odds


def basic_message(message):
    """Send basic text message to room."""
    return message
