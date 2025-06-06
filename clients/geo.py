"""User geo data client to identify bad actors."""

from typing import Union

import pandas as pd
import ipdata
from ipdata import IPData
from ipdata.ipdata import IPDataException
from pandas import DataFrame


class GeoIP:
    """Client for fetching geo data."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def client(self) -> IPData:
        """
        Return instantiated IP Data client.

        :returns: IPData
        """
        try:
            return ipdata.IPData(self.api_key)
        except IPDataException as e:
            print(f"IPData API threw an exception: {e}")
        except Exception as e:
            print(f"Unexpected exception while creating IPData client: {e}")

    def lookup_user_by_ip(self, ip_address: str) -> dict:
        """
        Fetch metadata associated with user's IP address.

        :param str ip_address: Chatango user's IP address.

        :returns: dict
        """
        try:
            return self.client.lookup(
                ip_address,
                fields=[
                    "ip",
                    "city",
                    "region",
                    "region_code",
                    "country_name",
                    "country_code",
                    "continent_name",
                    "latitude",
                    "longitude",
                    "asn",
                    "postal",
                    "calling_code",
                    "flag",
                    "emoji_flag",
                    "emoji_unicode",
                    "carrier",
                    "languages",
                    "currency",
                    "time_zone",
                    "threat",
                    "count",
                    "status",
                    "company",
                ],
            )
        except IPDataException as e:
            print(f"IPData API failed to lookup user with ip=ip_address: {e}")
        except Exception as e:
            print(f"Unexpected failure for IPData user lookup, ip={ip_address}: {e}")

    @staticmethod
    def save_metadata(room_name: str, user_name: str, ip_metadata: dict) -> Union[DataFrame, str]:
        """
        Parse IP metadata into Pandas Dataframe.

        :param str room_name: Chatango room.
        :param str user_name: Chatango user's username.
        :param dict ip_metadata: Metadata associated with a given message.

        :returns: DataFrame
        """
        try:
            record = {"username": user_name, "chatango_room": room_name}
            record.update(ip_metadata)
            metadata_df = pd.json_normalize([record], sep="_")
            metadata_df = metadata_df.infer_objects()
            metadata_df.astype(
                {
                    "username": "string",
                    "chatango_room": "string",
                    "ip": "string",
                    "city": "string",
                    "region": "string",
                    "country_name": "string",
                    "latitude": "float",
                    "longitude": "float",
                    "postal": "Int64",
                    "emoji_flag": "string",
                    "status": "Int64",
                    "time_zone_name": "string",
                    "time_zone_abbr": "string",
                    "time_zone_offset": "Int64",
                    "time_zone_is_dst": "Int8",
                    "carrier_name": "string",
                    "carrier_mnc": "string",
                    "carrier_mcc": "string",
                    "asn_asn": "string",
                    "asn_name": "string",
                    "asn_domain": "string",
                    "asn_route": "string",
                    "asn_type": "string",
                    "is_proxy": "boolean",
                    "is_anonymous": "boolean",
                    "is_tor": "boolean",
                    "is_known_attacker": "boolean",
                    "is_known_abuser": "boolean",
                    "is_bogon": "boolean",
                }
            )
            return metadata_df
        except Exception as e:
            return f"Could not parse user data for {user_name}: {e}"
