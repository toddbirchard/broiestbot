"""Database client."""
from typing import Optional, Tuple

from pandas import DataFrame
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Row
from sqlalchemy.exc import SQLAlchemyError


class Database:
    """Database client."""

    def __init__(self, uri: str, args: dict, users_table: str):
        self.db = create_engine(uri, connect_args=args, echo=False)
        self.users_table = users_table

    def fetch_weather_icon(self, weather_query: int) -> Optional[dict]:
        """
        Fetch all rows via query.

        :param int weather_query: SQL query to run against database.

        :returns: Optional[str]
        """
        try:
            query = text(f"SELECT * FROM weather WHERE code = '{weather_query}';")
            response = self.db.execute(query).first()
            if response is not None:
                return dict(response)
        except SQLAlchemyError as e:
            print(f"Failed to execute SQL query `{weather_query}`: {e}")
        except Exception as e:
            print(f"Failed to execute SQL query `{weather_query}`: {e}")

    def fetch_cmd_response(self, command_query: str) -> Optional[dict]:
        """
        Fetch a single row; typically used to verify whether a
        record already exists (ie: users).

        :param str command_query: SQL query to run against database.

        :returns: Optional[dict]
        """
        try:
            query = text(f"SELECT * FROM commands WHERE command = '{command_query}';")
            response = self.db.execute(query).fetchone()
            if response is not None:
                return dict(response)
        except SQLAlchemyError as e:
            print(
                f"SQLAlchemyError occurred when executing SQL query `{command_query}`: {e}"
            )
        except Exception as e:
            print(f"Failed to execute SQL query `{command_query}`: {e}")

    def fetch_user(self, room_name: str, user, message) -> Optional[Row]:
        """
        Run a SELECT query.

        :param str room_name: Chatango room.
        :param user: User responsible for triggering command.
        :param message: User submitted message.

        :returns: Optional[Row]
        """
        try:
            query = text(
                f"SELECT * FROM user WHERE username = '{user.name}' AND chatango_room = '{room_name}';"
            )
            return self.db.execute(query).fetchone()
        except SQLAlchemyError as e:
            print(f"SQLAlchemyError occurred while fetching user {user.name}: {e}")
        except Exception as e:
            print(f"Failed to execute SQL query while fetching user {user.name}: {e}")

    def insert_data_from_dataframe(self, df: DataFrame) -> Tuple[str, bool]:
        """
        Insert record into SQL table as a Dataframe consisting of a single row.

        :param DataFrame df: Pandas DataFrame.
        """
        try:
            df.to_sql("user", self.db, if_exists="append", index=False)
            return (
                f"Successfully inserted record for {df['username']} in {df['chatango_room']}",
                True,
            )
        except Exception as e:
            return f"Failed to save metadata: {e}", False
