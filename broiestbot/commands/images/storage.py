"""Fetch randomly selected meme image(s) from storage bucket."""

from random import randint
from datetime import datetime

from emoji import emojize
from google.cloud.exceptions import GoogleCloudError, NotFound

from clients import gcs
from config import GOOGLE_BUCKET_NAME, GOOGLE_BUCKET_URL
from logger import LOGGER


def fetch_random_image_from_gcs_bucket(subdirectory: str) -> str:
    """
    Get image from Google Cloud Storage bucket.

    :param str subdirectory: Bucket directory to fetch random image from.

    :returns: str
    """
    try:
        images = gcs.bucket.list_blobs(prefix=subdirectory)
        image_list = [image.name for image in images if "." in image.name]
        rand = randint(0, len(image_list) - 1)
        image = f"{GOOGLE_BUCKET_URL}{GOOGLE_BUCKET_NAME}/{image_list[rand]}"
        return image
    except NotFound as e:
        LOGGER.warning(f"GCS `NotFound` error when fetching image for `{subdirectory}`: {e}")
        return "⚠️ omfg bot just broke wtf did u do ⚠️"
    except GoogleCloudError as e:
        LOGGER.exception(f"GCS `GoogleCloudError` error when fetching image for `{subdirectory}`: {e}")
        return "⚠️ omfg bot just broke wtf did u do ⚠️"
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching random GCS image for `{subdirectory}`: {e}")
        return "⚠️ o shit i broke im a trash bot ⚠️"


def spam_random_images_from_gcs_bucket(subdirectory: str) -> str:
    """
    Get randomized image from Google Cloud Storage bucket; post 3 times.

    :param str subdirectory: Bucket directory to fetch random image from.

    :returns: str
    """
    try:
        response = []
        images = gcs.bucket.list_blobs(prefix=subdirectory)
        image_list = [image.name for image in images if "." in image.name]
        for i in range(3):
            response.append(f"{GOOGLE_BUCKET_URL}{GOOGLE_BUCKET_NAME}/{image_list[randint(0, len(image_list) - 1)]}")
        return " ".join(response)
    except GoogleCloudError as e:
        LOGGER.warning(f"GCS `GoogleCloudError` error when fetching image for `{subdirectory}`: {e}")
        return "⚠️ omfg bot just broke wtf did u do ⚠️"
    except Exception as e:
        LOGGER.warning(f"Unexpected error when fetching random GCS image for `{subdirectory}`: {e}")
        return "⚠️ o shit i broke im a trash bot ⚠️"


def gcs_count_images_in_bucket(subdirectory: str) -> str:
    """
    Get randomized image from Google Cloud Storage bucket; post 3 times.

    :param str subdirectory: Bucket directory from which to return total image count.

    :returns: str
    """
    try:
        response = "\n\n\n"
        images = gcs.bucket.list_blobs(prefix=subdirectory)
        image_list = [image.name for image in images if "." in image.name]
        if len(image_list) > 0:
            response += f"<b>{subdirectory.upper()} image count:</b>\n"
            response += f":keycap_#: {len(image_list)}"
            return emojize(response, language="en")
        return emojize(
            f":warning: uhhh I couldnt find any images for {subdirectory.upper()} :warning:",
            language="en",
        )
    except GoogleCloudError as e:
        LOGGER.warning(f"GCS `GoogleCloudError` error when fetching image for `{subdirectory}`: {e}")
        return "⚠️ omfg bot just broke wtf did u do ⚠️"
    except ValueError as e:
        LOGGER.warning(f"ValueError when fetching random GCS image for `{subdirectory}`: {e}")
        return "⚠️ omfg bot just broke wtf did u do ⚠️"
    except Exception as e:
        LOGGER.warning(f"Unexpected error when fetching random GCS image for `{subdirectory}`: {e}")
        return "⚠️ o shit i broke im a trash bot ⚠️"


def fetch_latest_image_from_gcs_bucket(subdirectory: str) -> str:
    """
    Get most recent image added to Google Cloud Storage bucket.

    :param str subdirectory: Bucket directory to fetch random image from.

    :returns: str
    """
    try:
        most_recent_image = sorted(
            [(blob, blob.updated) for blob in gcs.bucket.list_blobs(prefix=subdirectory)], key=lambda tup: tup[1]
        )[-1]
        return f"\n\n \
            {GOOGLE_BUCKET_URL}{GOOGLE_BUCKET_NAME}/{most_recent_image[0].name}\n \
            <b>{most_recent_image[0].name.split('/')[1].split('.')[0]}</b>\n \
            <i>(Added on {datetime.date(most_recent_image[1])})</i>"
    except GoogleCloudError as e:
        LOGGER.exception(f"GCS `GoogleCloudError` error when fetching image for `{subdirectory}`: {e}")
        return "⚠️ omfg bot just broke wtf did u do ⚠️"
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching random GCS image for `{subdirectory}`: {e}")
        return "⚠️ o shit i broke im a trash bot ⚠️"
