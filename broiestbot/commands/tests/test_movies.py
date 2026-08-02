"""Tests for OMDb movie lookups."""

import asyncio

from broiestbot.commands.movies import find_movie
from tests.aiohttp_mocks import FakeResponse, patch_http_session

# Trimmed OMDb response; only the fields `find_movie` reads are kept.
OMDB_MOVIE = {
    "Title": "Heat",
    "Year": "1995",
    "Rated": "R",
    "Actors": "Al Pacino, Robert De Niro",
    "Director": "Michael Mann",
    "Genre": "Crime, Drama, Thriller",
    "Plot": "A group of high-end professional thieves start to feel the heat.",
    "Poster": "https://example.test/heat.jpg",
    "Awards": "11 wins & 12 nominations",
    "BoxOffice": "$67,436,818",
    "imdbID": "tt0113277",
    "Ratings": [
        {"Source": "Internet Movie Database", "Value": "8.3/10"},
        {"Source": "Rotten Tomatoes", "Value": "87%"},
    ],
}


def _find(movie: dict) -> str:
    with patch_http_session("broiestbot.commands.movies", FakeResponse(json_data=movie)):
        return asyncio.run(find_movie("Heat"))


def test_rotten_tomatoes_rating_is_included():
    """The Rotten Tomatoes score is pulled out of the `Ratings` array by source name."""
    result = _find(OMDB_MOVIE)
    assert "Rotten Tomatos</b>: 87%" in result
    assert "HEAT" in result


def test_rating_is_matched_by_source_not_position():
    """A Rotten Tomatoes entry which isn't first in the array is still found."""
    ratings = [
        {"Source": "Metacritic", "Value": "76/100"},
        {"Source": "Internet Movie Database", "Value": "8.3/10"},
        {"Source": "Rotten Tomatoes", "Value": "87%"},
    ]
    assert "Rotten Tomatos</b>: 87%" in _find({**OMDB_MOVIE, "Ratings": ratings})


def test_movie_without_a_rotten_tomatoes_score_still_renders():
    """
    OMDb omits the Rotten Tomatoes entry for many titles. The rest of the movie's
    metadata must still be returned rather than the whole lookup blowing up.
    """
    ratings = [{"Source": "Internet Movie Database", "Value": "8.3/10"}]
    result = _find({**OMDB_MOVIE, "Ratings": ratings})
    assert "Rotten Tomatos" not in result
    assert "HEAT" in result
    assert "Michael Mann" in result


def test_movie_without_any_ratings_still_renders():
    """A response carrying no `Ratings` key at all is rendered without a rating line."""
    movie = {key: value for key, value in OMDB_MOVIE.items() if key != "Ratings"}
    result = _find(movie)
    assert "Rotten Tomatos" not in result
    assert "HEAT" in result
    assert "Al Pacino" in result


def test_empty_ratings_array_still_renders():
    """An empty `Ratings` array is treated the same as a missing one."""
    result = _find({**OMDB_MOVIE, "Ratings": []})
    assert "Rotten Tomatos" not in result
    assert "HEAT" in result
