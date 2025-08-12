"""Lookup movie information via IMDB API."""

from typing import Optional

import requests
from requests.exceptions import HTTPError
from emoji import emojize
from imdb import IMDbError
from imdb.Movie import Movie

from clients import ia
from logger import LOGGER

from config import STREAMING_SERVICE_ENDPOINT, STREAMING_SERVICE_HEADER, RAPID_API_KEY, HTTP_REQUEST_TIMEOUT


def find_imdb_movie(movie_title: str) -> str:
    """
    Get movie summary, rating, actors, poster, & box office info from IMDB.

    :param str movie_title: Movie to fetch IMDB info & box office info for.

    :returns: str
    """
    try:
        movies = ia.search_movie(movie_title)
        if bool(movies):
            movie_id = movies[0].getID()
            movie = ia.get_movie(movie_id)
            if movie:
                title = f"<b>{movie.data.get('title').upper()}</b>"
                cast = movie.data.get("cast")
                director = movie.data.get("director")
                year = movie.data.get("year")
                genres = movie.data.get("genres")
                rating = movie.data.get("rating")
                art = movie.data.get("cover url")
                box_office = get_box_office_data(movie)
                synopsis = movie.data.get("synopsis")
                if title and year:
                    title = f"{title} ({year})"
                if rating:
                    rating = f":star: <b>Rating</b>: {movie.data.get('rating')}/10"
                if cast:
                    cast = f":people_hugging: <b>Starring</b>: {', '.join([actor['name'] for actor in movie.data['cast'][:2]])}"
                if director:
                    director = f":clapper_board: <b>Directed by</b>: {movie.data.get('director')[0].get('name')}"
                if genres:
                    genres = f":movie_camera: <b>Genres</b>: {', '.join(movie.data.get('genres'))}"
                if synopsis:
                    synopsis = synopsis[0]
                    synopsis = " ".join(synopsis.split(". ")[:2])
                    synopsis = f":speech_balloon: <b>Description</b>: {synopsis}"
                response = "\n".join(
                    filter(
                        None,
                        [
                            title,
                            rating,
                            genres,
                            cast,
                            director,
                            synopsis,
                            box_office,
                            art,
                        ],
                    )
                )
                return emojize(f"\n\n\n{response}", language="en")
            return emojize(f":warning: wtf kind of movie is {movie} :warning:", language="en")
    except IMDbError as e:
        LOGGER.exception(f"IMDB failed to find `{movie_title}`: {e}")
        return emojize(f":warning: wtf kind of movie is {movie_title} :warning:", language="en")
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching IMDB movie `{movie_title}`: {e}")
        return emojize(":warning: omfg u broke me with ur shit movie :warning:", language="en")


def get_box_office_data(movie: Movie) -> Optional[str]:
    """
    Get IMDB box office performance for a given film.

    :param Movie movie: IMDB movie object.

    :returns: Optional[str]
    """
    try:
        response = []
        if movie.data.get("box office", None):
            budget = movie.data["box office"].get("Budget", None)
            opening_week = movie.data["box office"].get("Opening Weekend United States", None)
            gross = movie.data["box office"].get("Cumulative Worldwide Gross", None)
            if budget:
                response.append(f":money_bag: <b>Budget</b>: {budget}.")
            if opening_week:
                response.append(f":ticket: <b>Opening week</b>: {opening_week}.")
            if gross:
                response.append(f":globe_showing_Americas: <b>Worldwide gross</b>: {gross}")
            return "\n".join(response)
        LOGGER.warning(f"No IMDB box office info found for `{movie}`.")
    except KeyError as e:
        LOGGER.warning(f"KeyError when fetching box office info for `{movie}`: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching box office info for `{movie}`: {e}")


def streaming_service_show(tv_show_name: str) -> str:
    """
    Placeholder for future streaming service availability feature.

    :param str query: TV show to search for.

    :returns: str
    """
    try:
        params = {"title": tv_show_name, "country": "us", "output_language": "en", "show_type": "series"}
        headers = {"X-RapidAPI-Key": RAPID_API_KEY, "X-RapidAPI-Host": STREAMING_SERVICE_HEADER}
        resp = requests.get(STREAMING_SERVICE_ENDPOINT, headers=headers, params=params, timeout=HTTP_REQUEST_TIMEOUT)
        if resp.status_code == 200:
            show = resp.json()[0]
            response = ""
            response += streaming_service_show_description(show)
            return emojize(response, language="en")
    except HTTPError as e:
        LOGGER.exception(f"Streaming-availability API failed to find `{tv_show_name}`: {e}")
        return emojize(f":warning: wtf kind of show is {tv_show_name} :warning:", language="en")
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching show availability `{tv_show_name}`: {e}")
        return emojize(f":warning: wtf kind of show is {tv_show_name} :warning:", language="en")


def streaming_service_movie(movie_name: str) -> str:
    """
    Placeholder for future streaming service availability feature.

    :param str query: Movie to search for.

    :returns: str
    """
    pass


def streaming_service_show_description(result: dict) -> str:
    """
    Placeholder for future streaming service availability feature.

    :returns: str
    """
    # LOGGER.info(f"Streaming-availability API found: `{result}`")
    streaming_options = result.get("streamingOptions")
    streaming_options_us = streaming_options.get("us")
    if streaming_options is not None and streaming_options_us is not None:
        title = result.get("title", "Unknown Title")
        overview = result.get("overview", "No overview available.")
        first_air_date = result.get("firstAirYear", "Unknown release date")
        last_air_date = result.get("lastAirYear", "Unknown last air date")
        rating = result.get("rating", "No rating available")
        season_count = result.get("seasonCount", "Unknown number of seasons")
        episode_count = result.get("episodeCount", "Unknown number of episodes")
        image_set = result.get("imageSet")
        series_overview = f'\n\n\n<b>{title}</b> ({first_air_date} - {last_air_date})\n \
            <i>"{overview}"</i>\n \
            ⭐️ {rating} / 100\n \
            #️⃣ Seasons: {season_count}, Episodes: {episode_count}'
        if image_set is not None:
            horizontal_images = image_set.get("horizontalPoster")
            if horizontal_images is not None:
                image = horizontal_images.get("w360")
                if image is not None:
                    series_overview += f"\n\n {image} \n"
        service_dict = {}
        for service in streaming_options_us:
            if service["service"].get("name") and service.get("link"):
                service_name = service["service"]["name"]
                service_dict[service_name] = service["link"]
        for k, v in service_dict.items():
            series_overview += f"\n- {k}: {v}"
        return series_overview
    return ":warning: No streaming options available for ur trash show :warning:"
