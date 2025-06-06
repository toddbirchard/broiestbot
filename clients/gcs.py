"""Connect to remote Google Cloud Storage client."""

from google.cloud import storage
from google.cloud.storage import Blob


class GCS:
    """Google Cloud Storage manager."""

    def __init__(self, bucket_name, bucket_url):
        self.bucket_name = bucket_name
        self.bucket_url = bucket_url

    @property
    def client(self):
        """Get GCS client."""
        return storage.Client()

    @property
    def bucket(self):
        """Get GCS bucket."""
        return self.client.get_bucket(self.bucket_name)

    def upload_file(self, local_file, remote_file):
        """Upload local image to GCS bucket."""
        blob = Blob(remote_file, self.bucket)
        with open(local_file, "rb") as image:
            blob.upload_from_file(image)
        return self.bucket_url + self.bucket_name + "/" + blob.name
